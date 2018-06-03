from contextlib import contextmanager
import threading

import pyatspi

@contextmanager
def ConnectA11yController():
    controller = AtspiController()
    controller.start()
    yield controller
    controller.stop()

class AtspiController(object):
    def __init__(self):
        self._focused = None
        def update_focus(event):
            self._focused = AtspiObject(event.source)
        pyatspi.Registry.registerEventListener(update_focus,
                                               "object:state-changed:focused")

    def start(self):
        thread = threading.Thread(target=pyatspi.Registry.start)
        thread.start()

    def stop(self):
        pyatspi.Registry.stop()

    def get_focused_object(self):
        return self._focused

class AtspiObject(object):
    def __init__(self, object):
        self._object = object

    def is_editable(self):
        if pyatspi.state.STATE_EDITABLE not in self._object.getState().getStates():
            return False
        try:
            self._object.queryEditableText()
        except NotImplementedError:
            return False
        return True
