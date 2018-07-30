import sys
from contextlib import contextmanager

if sys.platform.startswith("win"):
    from . import ia2
    controller_class = ia2.Pyia2Controller
else:
    # TODO check if Linux.
    from . import atspi
    controller_class = atspi.AtspiController

@contextmanager
def ConnectA11yController():
    controller = controller_class()
    controller.start()
    yield controller
    controller.stop()
