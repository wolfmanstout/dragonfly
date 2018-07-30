import Queue
import threading


class Pyia2Controller(object):

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
        import pyia2

        # Set up event listeners.
        def update_focus(event):
            accessible_object = pyia2.accessibleObjectFromEvent(event)
            if not accessible_object:
                self.set_focused_object(None)
                return
            accessible2_object = pyia2.accessible2FromAccessible(accessible_object,
                                                                 pyia2.CHILDID_SELF)
            if not isinstance(accessible2_object, pyia2.IA2Lib.IAccessible2):
                self.set_focused_object(None)
                return
            self.set_focused_object(Pyia2Object(accessible2_object, self))

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
                        capture.return_value = capture.closure(pyia2)
                    except Exception as exception:
                        capture.exception = exception
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

    def get_focused_object(self):
        with self._lock:
            return self._focused

    def set_focused_object(self, object):
        with self._lock:
            self._focused = object
    

class Pyia2Object(object):
    def __init__(self, object, controller):
        self._object = object
        self._controller = controller

    def is_editable(self):
        return self._controller.run_sync(lambda pyia2: pyia2.IA2_STATE_EDITABLE & self._object.states)
