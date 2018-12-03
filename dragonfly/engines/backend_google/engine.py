from __future__ import division

from collections import Counter
import re
import sys
import threading

import aenea.config
import aenea.proxy_contexts
import aenea.proxy_actions
import aenea.strict
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import inflect
import pyaudio
from six.moves import queue
try:
    import win10toast
except ImportError:
    pass

from ... import get_stopping_accessibility_controller
from .dictation import GoogleSpeechDictationContainer
from .timer import SimpleTimerManager
from ..base import EngineBase
from ...grammar.state import State
try:
    from ...windows.window import Window
except ImportError:
    # TODO Fix when not using windows.
    pass


# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms


class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self._closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )
        self._closed = False
        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self._closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self, shutdown_event):
        while not self._closed and not shutdown_event.is_set():
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)


class GoogleSpeechEngine(EngineBase):

    _name = "google"
    DictationContainer = GoogleSpeechDictationContainer

    def __init__(self):
        super(GoogleSpeechEngine, self).__init__()
        self._connected = False
        self._timer_manager = SimpleTimerManager(0.02, self)
        self._inflect = inflect.engine()
        self._toaster = win10toast.ToastNotifier() if "win10toast" in sys.modules else None
        self._replacements = {
            r"\b(to|two)\b": ("to", "two"),
            r"\b(for|four)\b": ("for", "four"),
        }

    def toast(self, title, description):
        if not self._toaster:
            return
        thread = threading.Thread(target=lambda: self._toaster.show_toast(title, description, duration=2))
        thread.start()

    def _get_language(self):
        return "en"

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def _load_grammar(self, grammar):
        grammar.engine = self

        # Dependency checking.
        memo = []
        for r in grammar._rules:
            for d in r.dependencies(memo):
                grammar.add_dependency(d)

        return grammar

    def _unload_grammar(self, grammar, wrapper):
        pass

    def activate_rule(self, rule, grammar):
        pass

    def deactivate_rule(self, rule, grammar):
        pass

    def update_list(self, lst, grammar):
        pass

    def process_results_with_grammar(self, results, rule_set, grammar):
        func = getattr(grammar, "process_recognition", None)
        if func:
            words = [w for w, r in results]
            if not func(words):
                return False

        s = State(results, rule_set, self)
        for r in grammar._rules:
            if not r.active or not r.exported: continue
            s.initialize_decoding()
            for result in r.decode(s):
                if s.finished():
                    self._log.debug("Matching rule: %s" % r.name)
                    root = s.build_parse_tree()
                    r.process_recognition(root)
                    return True
        return False

    def generate_transcripts(self, original_transcript):
        """Generates alternative transcripts given a single transcript."""
        generators = [self.generate_number_transcripts]
        for (pattern, replacements) in self._replacements.items():
            generators.append(lambda transcript, pattern=pattern, replacements=replacements: self.generate_vocabulary_transcripts(transcript, pattern, replacements))
        transcripts = [original_transcript]
        for generator in generators:
            new_transcripts = []
            for transcript in transcripts:
                generated_transcripts = generator(transcript)
                if len(generated_transcripts) > 0:
                    new_transcripts.extend(generated_transcripts)
                else:
                    new_transcripts.append(transcript)
            transcripts = new_transcripts
        return transcripts

    def generate_number_transcripts(self, transcript):
        transcripts = []
        (replaced, num_replaced) = re.subn(r"\d+", lambda match: re.sub(r"\W", " ", self._inflect.number_to_words(match.group(0))), transcript)
        if num_replaced == 0:
            return []
        transcripts.append(replaced)
        replaced = re.sub(r"\d+", lambda match: re.sub(r"\W", " ", self._inflect.number_to_words(match.group(0), group=1)), transcript)
        transcripts.append(replaced)
        return transcripts

    def generate_vocabulary_transcripts(self, transcript, pattern, replacements):
        transcripts = []
        for replacement in replacements:
            (replaced, num_replaced) = re.subn(pattern, replacement, transcript)
            if num_replaced == 0:
                return []
            transcripts.append(replaced)
        return transcripts


    def process_transcript(self, transcript):
        results = [(word, 0) for word in transcript.split()]
        for (_, grammar) in self._grammar_wrappers.items():
            if self.process_results_with_grammar(results, ["dgndictation"], grammar):
                return True
        return False


    def get_stable_transcript(self, response):
        """Gets the transcript from the response if relatively stable, otherwise returns
        None. This is fast but not always accurate or complete.
        """
        if not all(result.is_final or result.stability > 0.5 for result in response.results):
            return None
        return "".join(result.alternatives[0].transcript for result in response.results)


    def get_final_transcript(self, response):
        """Gets the transcript from the response if final, otherwise returns None. This
        is accurate but slow.
        """
        if not all(result.is_final for result in response.results):
            return None
        return "".join(result.alternatives[0].transcript for result in response.results)


    def get_foreground(self):
        """Gets the foreground window information a cross-platform way using Aenea."""
        if aenea.config.proxy_active():
            context = aenea.proxy_contexts._get_context()
            return dict(title=context["title"], executable=context["executable"], handle="")
        else:
            window = Window.get_foreground()
            return dict(title=window.title, executable=window.executable, handle=window.handle)


    def process_responses(self, responses, shutdown_event):
        processed_transcript = False
        for response in responses:
            if processed_transcript:
                continue
            if response.speech_event_type == enums.StreamingRecognizeResponse.SpeechEventType.END_OF_SINGLE_UTTERANCE:
                self._log.debug("End of utterance")
                # Shut down this request so that new audio is buffered for the next request.
                shutdown_event.set()
            if not response.results:
                continue

            transcript = self.get_stable_transcript(response)
            if transcript:
                # Shut down this request so that new audio is buffered for the next request.
                shutdown_event.set()
                self._log.debug("Transcript: " + transcript)
                # Exit recognition if any of the transcribed phrases could be
                # one of our keywords.
                if re.match(r"\s*dragonfly close now\s*", transcript, re.I):
                    print('Exiting..')
                    return False
                for (_, grammar) in self._grammar_wrappers.items():
                    context = self.get_foreground()
                    grammar.process_begin(**context)
                self._log.debug("Prepared grammar")
                candidates = self.generate_transcripts(transcript)
                success = False
                for candidate in candidates:
                    self._log.debug("Candidate: " + candidate)
                    if self.process_transcript(candidate):
                        self._log.debug("Succeeded")
                        # self.toast("Succeeded", candidate)
                        success = True
                        break
                if not success:
                    # Dictate into editable text widget.
                    if self._accessibility.is_editable_focused():
                        # TODO Escape transcript.
                        aenea.strict.Text(transcript).execute()
                        self._log.debug("Entered text into editable")
                        success = True
                if not success:
                    self._log.debug("Failed")
                    self.toast("Failed", transcript)
                processed_transcript = True
        return True


    def process_speech(self):
        # See http://g.co/cloud/speech/docs/languages
        # for a list of supported languages.
        language_code = 'en-US'  # a BCP-47 language tag

        client = speech.SpeechClient()
        config = types.RecognitionConfig(
            encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code=language_code)
        streaming_config = types.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
            single_utterance=True,
        )

        self.connect()
        with get_stopping_accessibility_controller() as accessibility:
            self._accessibility = accessibility
            with MicrophoneStream(RATE, CHUNK) as stream:
                while self._connected:
                    shutdown_event = threading.Event()
                    audio_generator = stream.generator(shutdown_event)
                    requests = (types.StreamingRecognizeRequest(audio_content=content)
                                for content in audio_generator)

                    # Add context phrases.
                    context_phrases = Counter()
                    for (_, grammar) in self._grammar_wrappers.items():
                        # window = Window.get_foreground()
                        # grammar.process_begin(window.executable, window.title,
                        #                       window.handle)
                        grammar.process_begin("", "", "")
                        for rule in grammar._rules:
                            if not rule.active or not rule.exported: continue
                            context_phrases.update(rule.element.context_phrases())
                    config = streaming_config.config
                    del config.speech_contexts[:]
                    speech_context = config.speech_contexts.add()
                    self._log.debug("Total phrases: %s", len(context_phrases))
                    # The API currently restricts to max 500 phrases as of 11/4/2017.
                    speech_context.phrases.extend(
                        sorted(w for w, c in context_phrases.most_common(500)))
                    # self._log.debug("Phrases: %s", speech_context.phrases)

                    responses = client.streaming_recognize(streaming_config, requests)

                    # Now, put the transcription responses to use.
                    if not self.process_responses(responses, shutdown_event):
                        return
