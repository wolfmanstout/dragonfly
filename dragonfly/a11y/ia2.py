import Queue
import threading
import traceback


class Controller(object):

    class Capture(object):
        def __init__(self, closure):
            self.closure = closure
            self.done_event = threading.Event()
            self.exception = None
            self.return_value = None
    
    def __init__(self):
        self._focused = None
        # TODO Replace with a completely synchronous queue (size 0).
        self._closure_queue = Queue.Queue(1)
        self._lock = threading.Lock()

    def _start_blocking(self):
        # Import here so that it can be used in a background thread. The import
        # must be run in the same thread as event registration and handling.
        global pyia2
        import pyia2

        # Set up event listeners.
        def update_focus(event):
            accessible = pyia2.accessibleObjectFromEvent(event)
            if not accessible:
                self._set_focused(None)
                return
            accessible2 = pyia2.accessible2FromAccessible(accessible,
                                                          pyia2.CHILDID_SELF)
            if not isinstance(accessible2, pyia2.IA2Lib.IAccessible2):
                self._set_focused(None)
                return
            self._set_focused(Accessible(accessible2, self))

        pyia2.Registry.registerEventListener(update_focus,
                                             pyia2.EVENT_OBJECT_FOCUS)

        # Process events.
        while not self.shutdown_event.is_set():
            pyia2.Registry.iter_loop(0.01)
            # TODO Register this directly in iter_loop to avoid waiting.
            try:
                while True:
                    capture = self._closure_queue.get_nowait()
                    try:
                        capture.return_value = capture.closure()
                    except Exception as exception:
                        capture.exception = exception
                        # The stack trace won't be captured, so print here.
                        traceback.print_exc()
                    capture.done_event.set()
            except Queue.Empty:
                pass
                
    def start(self):
        self.shutdown_event = threading.Event()
        thread = threading.Thread(target=self._start_blocking)
        thread.start()

    def stop(self):
        self.shutdown_event.set()

    def run_sync(self, closure):
        capture = self.Capture(closure)
        self._closure_queue.put(capture)
        capture.done_event.wait()
        if capture.exception:
            raise capture.exception
        return capture.return_value

    def get_focused(self):
        with self._lock:
            return self._focused

    def _set_focused(self, accessible):
        with self._lock:
            self._focused = accessible
    

# TODO Rethink separation into object accessible outside of ia2 thread.
class Accessible(object):
    def __init__(self, accessible, controller):
        self._accessible = accessible
        self._controller = controller

    def _create_accessible_text(self):
        # TODO Handle exceptions.
        text = self._accessible.QueryInterface(pyia2.IA2Lib.IAccessibleText)
        return AccessibleTextNode(text)

    def is_editable(self):
        return self._controller.run_sync(lambda: pyia2.IA2_STATE_EDITABLE & self._accessible.states)

    def manipulate_text(self, callback):
        return self._controller.run_sync(lambda: callback(self._create_accessible_text()))

class AccessibleTextNode(object):
    def __init__(self, accessible_text):
        self._text = accessible_text
        self._children = []
        text_length = self._text.nCharacters
        text = self._text.text(0, text_length) if text_length > 0 else ""
        expanded_text_pieces = []
        child_indices = [i for i, c in enumerate(text) if c == u"\ufffc"]
        if len(child_indices) == 0:
            self._add_leaf(0, text_length, text, expanded_text_pieces, True)
        elif child_indices[0] > 0:
            self._add_leaf(0, child_indices[0], text, expanded_text_pieces, False)
        for i, child_index in enumerate(child_indices):
            # TODO Handle case where all embedded objects are non-text and this interface is not supported.
            hypertext = self._text.QueryInterface(pyia2.IA2Lib.IAccessibleHypertext)
            hyperlink_index = hypertext.hyperlinkIndex(child_index)
            hyperlink = hypertext.hyperlink(hyperlink_index)
            # TODO Handle case where embedded object is non-text.
            child = hyperlink.QueryInterface(pyia2.IA2Lib.IAccessibleText)
            child_node = AccessibleTextNode(child)
            self._children.append(child_node)
            expanded_text_pieces.append(child_node.expanded_text)
            end_index = child_indices[i + 1] if i < len(child_indices) - 1 else text_length
            if end_index > child_index + 1:
                self._add_leaf(child_index + 1, end_index, text, expanded_text_pieces, i == len(child_indices) - 1)
        self.expanded_text = "".join(expanded_text_pieces)
    
    def _add_leaf(self, start, end, text, expanded_text_pieces, is_last):
        child = AccessibleTextLeaf(self._text, text, start, end, is_last)
        self._children.append(child)
        expanded_text_pieces.append(child.expanded_text)

    def to_string(self):
        return "(" + ", ".join(child.to_string() for child in self._children) + ")"

    def set_cursor(self, offset):
        for child in self._children:
            if offset < len(child.expanded_text):
                child.set_cursor(offset)
                return
            offset -= len(child.expanded_text)

    def get_cursor(self):
        pass
        # TODO Implement.

class AccessibleTextLeaf(object):
    DELIMITER = "\x1e"

    def __init__(self, accessible_text, text, start, end, is_last):
        self._text = accessible_text
        self.expanded_text = text[start:end]
        if is_last:
            self.expanded_text += self.DELIMITER
        self._start = start
        self._end = end

    def to_string(self):
        return self.expanded_text
        
    def set_cursor(self, offset):
        # print "set_cursor: %s, %s" % (offset, self.expanded_text)
        self._text.setCaretOffset(self._start + offset)

    def get_cursor(self):
        pass
        # TODO Implement.
