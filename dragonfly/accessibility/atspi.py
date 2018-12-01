import threading

import pyatspi

class Controller(object):
    def __init__(self):
        self._focused = None
        def update_focus(event):
            # TODO Add concurrency control.
            self._focused = Accessible(event.source)
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

    def get_focused(self):
        return self._focused

class Accessible(object):
    def __init__(self, accessible):
        self._accessible = accessible

    def is_editable(self):
        if pyatspi.state.STATE_EDITABLE not in self._accessible.getState().getStates():
            return False
        try:
            self._accessible.queryEditableText()
        except NotImplementedError:
            return False
        return True
