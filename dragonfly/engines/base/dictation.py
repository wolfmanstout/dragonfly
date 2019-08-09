#
# This file is part of Dragonfly.
# (c) Copyright 2007, 2008 by Christo Butcher
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
Dictation container base class
============================================================================

This class is used to store the recognized results of dictation elements 
within voice-commands.  It offers access to both the raw spoken-form words 
and be formatted written-form text.

The formatted text can be retrieved using
:meth:`~DictationContainerBase.format` or simply by  calling ``str(...)``
on a dictation container object. A tuple of the raw  spoken words can be
retrieved using :attr:`~DictationContainerBase.words`.


String Formatting Examples
----------------------------------------------------------------------------

The following examples demonstrate dictation input can be formatted by
calling string methods on :class:`Dictation` elements.

Python example:

..  code:: python

    mapping = {
        # Define commands for writing Python methods, functions and classes.
        "method [<under>] <snaketext>":
            Text("def %(under)s%(snaketext)s(self):") + Key("left:2"),
        "function <snaketext>":
            Text("def %(snaketext)s():") + Key("left:2"),
        "classy [<classtext>]":
            Text("class %(classtext)s:") + Key("left"),

        # Define a command for accessing object members.
        "selfie [<under>] [<snaketext>]":
            Text("self.%(under)s%(snaketext)s"),
    }

    extras = [
        # Define a Dictation element that produces snake case text,
        # e.g. hello_world.
        Dictation("snaketext", default="").lower().replace(" ", "_"),

        # Define a Dictation element that produces text matching Python's
        # class casing, e.g. DictationContainer.
        Dictation("classtext", default="").title().replace(" ", ""),

        # Allow adding underscores before cased text.
        Choice("under", {"under": "_"}, default=""),
    ]

    rule = MappingRule(name="PythonExample", mapping=mapping, extras=extras)


Markdown example:

..  code:: python

    mapping = {
        # Define a command for typing Markdown headings 1 to 7 with optional
        # capitalized text.
        "heading [<num>] [<capitalised_text>]":
            Text("#")*Repeat("num") + Text(" %(capitalised_text)s"),
    }

    extras = [
        Dictation("capitalised_text", default="").capitalize(),
        IntegerRef("num", 1, 7, 1),
    ]

    rule = MappingRule(name="MdExample", mapping=mapping, extras=extras)


Camel-case example using the :meth:`Dictation.camel` method:

..  code:: python

    mapping = {
        # Define a command for typing camel-case text, e.g. helloWorld.
        "camel <camel_text>": Text(" %(camel_text)s"),
    }

    extras = [
        Dictation("camel_text", default="").camel(),
    ]

    rule = MappingRule(name="CamelExample", mapping=mapping, extras=extras)


Example using the :meth:`Dictation.apply` method for random casing:

..  code:: python

    from random import random

    def random_text(text):
        # Randomize the case of each character.
        result = ""
        for c in text:
            r = random()
            if r < 0.5:
                result += c.lower()
            else:
                result += c.upper()
        return result

    mapping = {
        "random <random_text>": Text("%(random_text)s"),
    }

    extras = [
        Dictation("random_text", default="").apply(random_text),
    ]

    rule = MappingRule(name="RandomExample", mapping=mapping, extras=extras)


Class reference
----------------------------------------------------------------------------

"""


#---------------------------------------------------------------------------
# Dictation base class -- base class for SR engine-specific containers
#  of dictated words.
import locale

from six import PY2


class DictationContainerBase(object):
    """
        Container class for dictated words as recognized by the
        :class:`Dictation` element.

        This base class implements the general functionality of dictation 
        container classes.  Each supported engine should have a derived 
        dictation container class which performs the actual engine-
        specific formatting of dictated text.

    """

    def __init__(self, words):
        """
            A dictation container is created by passing it a sequence
            of words as recognized by the backend SR engine.
            Each word must be a Unicode string.

            :param words: A sequence of Unicode strings.
            :type words: sequence-of-unicode

        """
        self._words = tuple(words)
        self._formatted = None

    def __str__(self):
        if self._formatted is None:
            self._formatted = self.format()
        return self._formatted

    def __unicode__(self):
        if self._formatted is None:
            self._formatted = self.format()
        return self._formatted

    def __repr__(self):
        message = u"%s(%s)" % (self.__class__.__name__,
                               u", ".join(self._words))
        if PY2:
            return message.encode(locale.getpreferredencoding())
        else:
            return message

    @property
    def words(self):
        """ Sequence of the words forming this dictation. """
        return self._words

    def format(self):
        """ Format and return this dictation as a Unicode object. """
        return u" ".join(self._words)
