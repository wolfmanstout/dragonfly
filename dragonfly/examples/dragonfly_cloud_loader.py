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
Command-module loader for Google Cloud Speech API.
"""


import os
import os.path
import logging
import sys
import traceback

from dragonfly.engines.backend_google.engine import GoogleSpeechEngine
import dragonfly.log


#---------------------------------------------------------------------------
# Command module class; wraps a single command-module.

class CommandModule(object):

    _log = logging.getLogger("module")

    def __init__(self, path):
        self._path = os.path.abspath(path)
        self._namespace = {}
        self._loaded = False

    def __str__(self):
        return "%s(%r)" % (self.__class__.__name__,
                           os.path.basename(self._path))

    def load(self):
        self._log.info("%s: Loading module: '%s'" % (self, self._path))

        # Prepare namespace in which to execute the module.
        namespace = {}
        namespace["__file__"] = self._path

        # Attempt to execute the module; handle any exceptions.
        try:
            execfile(self._path, namespace)
        except Exception, e:
            self._log.error("%s: Error loading module: %s" % (self, traceback.format_exc()))
            self._loaded = False
            return

        self._loaded = True
        self._namespace = namespace

    def unload(self):
        self._log.info("%s: Unloading module: '%s'" % (self, self._path))
        if "unload" in self._namespace:
            self._namespace["unload"]()


#---------------------------------------------------------------------------
# Command module directory class.

class CommandModuleDirectory(object):

    _log = logging.getLogger("directory")

    def __init__(self, path, excludes=None):
        self._path = os.path.abspath(path)
        self._excludes = excludes
        self._modules = {}

    def load(self):
        valid_paths = self._get_valid_paths()

        # Remove any deleted modules.
        for path, module in self._modules.items():
            if path not in valid_paths:
                del self._modules[path]
                module.unload()

        # Add any new modules.
        for path in valid_paths:
            if path not in self._modules:
                module = CommandModule(path)
                module.load()
                self._modules[path] = module
            else:
                module = self._modules[path]

    def unload(self):
        for path, module in self._modules.items():
            del self._modules[path]
            module.unload()

    def _get_valid_paths(self):
        self._log.info("Looking for command modules here: %s" % (self._path,))
        valid_paths = []
        for filename in os.listdir(self._path):
            path = os.path.abspath(os.path.join(self._path, filename))
            if not os.path.isfile(path):
                continue
            if not os.path.splitext(path)[1] == ".py":
                continue
            if not os.path.basename(path).startswith("_"):
                continue
            if path in self._excludes:
                continue
            valid_paths.append(path)
        self._log.info("Valid paths: %s" % (", ".join(valid_paths),))
        return valid_paths


#---------------------------------------------------------------------------
# Main event driving loop.

def main():
    logging.basicConfig(level=logging.INFO)
    dragonfly.log.default_levels["engine"] = (logging.DEBUG, logging.DEBUG)
    dragonfly.log.setup_log()

    engine = GoogleSpeechEngine()
    engine.connect()

    if "DRAGONFLY_USER_DIRECTORY" in os.environ:
        path = os.environ["DRAGONFLY_USER_DIRECTORY"]
    else:
        path = ""
    sys.path.insert(0, path)
    directory = CommandModuleDirectory(path, excludes=[])
    directory.load()
    engine.process_speech()
    directory.unload()


if __name__ == "__main__":
    # Fix issue where process hangs and is unresponsive to Ctrl-C after
    # exception is thrown.
    try:
        main()
    except:
        traceback.print_exc()
        os._exit(-1)
