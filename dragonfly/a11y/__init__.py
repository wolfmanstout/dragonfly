import sys
from contextlib import contextmanager

from .base import *

if sys.platform.startswith("win"):
    from . import ia2
    controller_class = ia2.Controller
else:
    # TODO check if Linux.
    from . import atspi
    controller_class = atspi.Controller

controller = None

# TODO Fix naming.
def GetA11yController():
    global controller
    if not controller:
        controller = controller_class()
        controller.start()
    return controller

# TODO Rethink ownership model.
@contextmanager
def ConnectA11yController():
    controller = GetA11yController()
    yield controller
    controller.stop()
