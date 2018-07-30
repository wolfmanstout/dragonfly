import threading

import pyatspi

class AtspiController(object):
    def __init__(self):
        self._focused = None
        def update_focus(event):
            # TODO Add concurrency control.
            self._focused = AtspiObject(event.source)
        pyatspi.Registry.registerEventListener(update_focus,
                                               "object:state-changed:focused")

    def start(self):
        thread = threading.Thread(target=pyatspi.Registry.start)
        thread.start()

    def stop(self):
        # TODO this is supposed to be called within an event handler in the GLib
        # main loop. Set up a way to send these using something similar to this:
        # https://github.com/GNOME/pyatspi2/blob/master/pyatspi/registry.py#L148
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
