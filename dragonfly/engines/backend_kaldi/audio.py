#
# This file is part of Dragonfly.
# (c) Copyright 2019 by David Zurow
# Licensed under the LGPL.
#
#   Dragonfly is free software: you can redistribute it and/or modify it
#   under the terms of the GNU Lesser General Public License as published
#   by the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   Dragonfly is distributed in the hope that it will be useful, but
#   WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with Dragonfly.  If not, see
#   <http://www.gnu.org/licenses/>.
#

"""
Audio input/output classes for Kaldi backend
"""

from __future__ import division
import collections, wave, logging, os, datetime, time
from io import open

from six import binary_type, text_type, print_
from six.moves import queue, range
import pyaudio
import webrtcvad

from ..base import EngineError

_log = logging.getLogger("engine")


class MicAudio(object):
    """Streams raw audio from microphone. Data is received in a separate thread, and stored in a buffer, to be read from."""

    FORMAT = pyaudio.paInt16
    RATE = 16000
    CHANNELS = 1
    BLOCKS_PER_SECOND = 50

    def __init__(self, callback=None, buffer_s=0, flush_queue=True, start=True, input_device_index=None):
        self.callback = callback if callback is not None else lambda in_data: self.buffer_queue.put(in_data, block=False)
        self.flush_queue = flush_queue
        self.input_device_index = input_device_index

        self.sample_rate = self.RATE
        self.buffer_queue = queue.Queue(maxsize=(buffer_s * 1000 // self.block_duration_ms))
        self.pa = pyaudio.PyAudio()
        self._connect(start=start)

    def _connect(self, start=None):
        callback = self.callback
        def proxy_callback(in_data, frame_count, time_info, status):
            callback(in_data)
            return (None, pyaudio.paContinue)
        self.stream = self.pa.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.block_size,
            stream_callback=proxy_callback,
            input_device_index=self.input_device_index,
            start=bool(start),
        )
        self.active = True
        info = self.pa.get_default_input_device_info() if self.input_device_index is None else self.pa.get_device_info_by_index(self.input_device_index)
        _log.info("streaming audio from '%s': %i sample_rate, %i block_duration_ms", info['name'], self.sample_rate, self.block_duration_ms)

    def destroy(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
        self.active = False

    block_size = property(lambda self: int(self.sample_rate / float(self.BLOCKS_PER_SECOND)), doc="Block size in number of samples")
    block_duration_ms = property(lambda self: int(1000 * self.block_size // self.sample_rate), doc="Block duration in milliseconds")

    def reconnect(self):
        self.stream.stop_stream()
        self.stream.close()
        self._connect(start=True)

    def start(self):
        self.stream.start_stream()

    def stop(self):
        self.stream.stop_stream()

    def read(self, nowait=False):
        """Return a block of audio data. If nowait==False, waits for a block if necessary; else, returns False immediately if no block is available."""
        if self.active or (self.flush_queue and not self.buffer_queue.empty()):
            if nowait:
                try:
                    return self.buffer_queue.get_nowait()  # Return good block if available
                except queue.Empty as e:
                    return False  # Queue is empty for now
            else:
                return self.buffer_queue.get()  # Wait for a good block and return it
        else:
            return None  # We are done

    def read_loop(self, callback):
        """Block looping reading, repeatedly passing a block of audio data to callback."""
        for block in iter(self):
            callback(block)

    def iter(self, nowait=False):
        """Generator that yields all audio blocks from microphone."""
        while True:
            block = self.read(nowait=nowait)
            if block is None:
                break
            yield block

    def __iter__(self):
        """Generator that yields all audio blocks from microphone."""
        return self.iter()

    def get_wav_length_s(self, data):
        assert isinstance(data, binary_type)
        length_bytes = len(data)
        assert self.FORMAT == pyaudio.paInt16
        length_samples = length_bytes / 2
        return (float(length_samples) / self.sample_rate)

    def write_wav(self, filename, data):
        # _log.debug("write wav %s", filename)
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.CHANNELS)
        # wf.setsampwidth(self.pa.get_sample_size(FORMAT))
        assert self.FORMAT == pyaudio.paInt16
        wf.setsampwidth(2)
        wf.setframerate(self.sample_rate)
        wf.writeframes(data)
        wf.close()

    @staticmethod
    def print_list():
        pa = pyaudio.PyAudio()

        print_("")
        print_("LISTING ALL INPUT DEVICES SUPPORTED BY PORTAUDIO")
        print_("(any device numbers not shown are for output only)")
        print_("")

        for i in range(0, pa.get_device_count()):
            info = pa.get_device_info_by_index(i)

            if info['maxInputChannels'] > 0:  # microphone? or just speakers
                print_("DEVICE #%d" % info['index'])
                print_("    %s" % info['name'])
                print_("    input channels = %d, output channels = %d, defaultSampleRate = %d" %
                    (info['maxInputChannels'], info['maxOutputChannels'], info['defaultSampleRate']))
                # print_(info)
                try:
                  supports16k = pa.is_format_supported(16000,  # sample rate
                      input_device = info['index'],
                      input_channels = info['maxInputChannels'],
                      input_format = pyaudio.paInt16)
                except ValueError:
                  print_("    NOTE: 16k sampling not supported, configure pulseaudio to use this device")

        print_("")


class VADAudio(MicAudio):
    """Filter & segment audio with voice activity detection."""

    def __init__(self, aggressiveness=3, **kwargs):
        super(VADAudio, self).__init__(**kwargs)
        self.vad = webrtcvad.Vad(aggressiveness)

    def vad_collector(self, padding_start_ms=300, padding_end_ms=100, complex_padding_end_ms=None, ratio=0.8, blocks=None, nowait=False):
        """Generator/coroutine that yields series of consecutive audio blocks comprising each phrase, separated by yielding a single None.
            Determines voice activity by ratio of blocks in padding_ms. Uses a buffer to include padding_ms prior to being triggered.
            Example: (block, ..., block, None, block, ..., block, None, ...)
                      |----phrase-----|        |----phrase-----|
        """
        num_padding_start_blocks = max(1, int((padding_start_ms / ratio) // self.block_duration_ms))
        num_padding_end_blocks = max(1, int((padding_end_ms / ratio) // self.block_duration_ms))
        num_complex_padding_end_blocks = max(1, int(((complex_padding_end_ms or padding_end_ms) / ratio) // self.block_duration_ms))
        audio_reconnect_threshold_blocks = 5
        audio_reconnect_threshold_time = 50 * self.block_duration_ms / 1000
        _log.debug("%s: vad_collector: num_padding_start_blocks=%s num_padding_end_blocks=%s num_complex_padding_end_blocks=%s",
            self, num_padding_start_blocks, num_padding_end_blocks, num_complex_padding_end_blocks)

        if blocks is None: blocks = self.iter(nowait=nowait)
        start_buffer = collections.deque(maxlen=num_padding_start_blocks)
        end_buffer = collections.deque(maxlen=num_padding_end_blocks)
        complex_end_buffer = collections.deque(maxlen=num_complex_padding_end_blocks)
        triggered = False
        in_complex_phrase = False
        num_empty_blocks = 0
        last_good_block_time = time.time()

        for block in blocks:
            if block is False or block is None:
                num_empty_blocks += 1
                if (num_empty_blocks >= audio_reconnect_threshold_blocks) and (time.time() - last_good_block_time >= audio_reconnect_threshold_time):
                    _log.warning("%s: no good block received recently, so reconnecting audio")
                    self.reconnect()
                    num_empty_blocks = 0
                    last_good_block_time = time.time()
                in_complex_phrase = yield block

            else:
                num_empty_blocks = 0
                last_good_block_time = time.time()
                is_speech = self.vad.is_speech(block, self.sample_rate)

                if not triggered:
                    # Between phrases
                    start_buffer.append((block, is_speech))
                    num_voiced = len([1 for block, speech in start_buffer if speech])
                    if num_voiced > ratio * start_buffer.maxlen:
                        # Start of phrase
                        triggered = True
                        for block, _ in start_buffer:
                            in_complex_phrase = yield block
                        start_buffer.clear()

                else:
                    # Ongoing phrase
                    in_complex_phrase = yield block
                    end_buffer.append((block, is_speech))
                    complex_end_buffer.append((block, is_speech))
                    num_unvoiced = len([1 for block, speech in end_buffer if not speech])
                    num_complex_unvoiced = len([1 for block, speech in complex_end_buffer if not speech])
                    if (not in_complex_phrase and num_unvoiced > ratio * end_buffer.maxlen) or (in_complex_phrase and num_complex_unvoiced > ratio * complex_end_buffer.maxlen):
                        # End of phrase
                        triggered = False
                        in_complex_phrase = yield None
                        end_buffer.clear()
                        complex_end_buffer.clear()


class AudioStore(object):
    """
    Stores the current audio data being recognized, which is cleared upon calling `finalize()`.
    Also, optionally stores the last `maxlen` recognitions as lists [audio, text, grammar_name, rule_name, misrecognition],
    indexed in reverse order (0 is most recent), and advanced upon calling `finalize()`.
    Note: `finalize()` should be called after the recognition has been parsed and its actions executed.
    """

    def __init__(self, audio_obj, maxlen=None, save_dir=None, auto_save_predicate_func=None):
        self.audio_obj = audio_obj
        self.maxlen = maxlen
        self.save_dir = save_dir
        if self.save_dir:
            _log.info("retaining audio and recognition metadata to '%s'", self.save_dir)
        self.auto_save_predicate_func = auto_save_predicate_func
        self.deque = collections.deque(maxlen=maxlen) if maxlen else None
        self.blocks = []

    current_audio_data = property(lambda self: b''.join(self.blocks))

    def add_block(self, block):
        self.blocks.append(block)

    def finalize(self, text, grammar_name, rule_name, likelihood=None):
        entry = AudioStoreEntry(self.current_audio_data, grammar_name, rule_name, text, likelihood, False)
        if self.deque is not None:
            if len(self.deque) == self.deque.maxlen:
                self.save(-1)  # Save oldest, which is about to be evicted
            self.deque.appendleft(entry)
        # if self.auto_save_predicate_func and self.auto_save_predicate_func(*entry):
        #     self.save(0)
        self.blocks = []

    def save(self, index):
        if slice(index).indices(len(self.deque))[1] >= len(self.deque):
            raise EngineError("Invalid index to save in AudioStore")
        if not self.save_dir:
            return
        if not os.path.isdir(self.save_dir):
            _log.warning("Audio was not retained because '%s' was not a directory" % self.save_dir)
            return

        filename = os.path.join(self.save_dir, "retain_%s.wav" % datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f"))
        entry = self.deque[index]
        self.audio_obj.write_wav(filename, entry.audio)
        with open(os.path.join(self.save_dir, "retain.tsv"), 'a', encoding='utf-8') as tsv_file:
            tsv_file.write(u'\t'.join([
                    filename,
                    text_type(self.audio_obj.get_wav_length_s(entry.audio)),
                    entry.grammar_name,
                    entry.rule_name,
                    entry.text,
                    text_type(entry.likelihood),
                    text_type(entry.misrecognition),
                ]) + '\n')

    def save_all(self):
        for i in reversed(range(len(self.deque))):
            self.save(i)

    def __getitem__(self, key):
        return self.deque[key]
    def __len__(self):
        return len(self.deque)
    def __bool__(self):
        return True
    def __nonzero__(self):
        return True

class AudioStoreEntry(object):
    __slots__ = ('audio', 'grammar_name', 'rule_name', 'text', 'likelihood', 'misrecognition')

    def __init__(self, audio, grammar_name, rule_name, text, likelihood, misrecognition):
        self.audio = audio
        self.grammar_name = grammar_name
        self.rule_name = rule_name
        self.text = text
        self.likelihood = likelihood
        self.misrecognition = misrecognition

    def set(self, key, value):
        setattr(self, key, value)
