from lark import Lark, Transformer
from ..grammar.elements_basic import Literal, Optional, Sequence, Alternative, Empty
import os

dir_path = os.path.dirname(os.path.realpath(__file__))

spec_parser = Lark.open(os.path.join(dir_path, "grammar.lark"),
    parser="lalr"
)

class ParseError(Exception):
    pass

class CompoundTransformer(Transformer):
    """
        Visits each node of the parse tree starting with the leaves
        and working up, replacing lark Tree objects with the
        appropriate dragonfly classes.
    """

    def __init__(self, extras=None, *args, **kwargs):
        self.extras = extras or {}
        Transformer.__init__(self, *args, **kwargs)

    def optional(self, args):
        return Optional(args[0])

    def literal(self, args):
        return Literal(" ".join(args))

    def sequence(self, args):
        return Sequence(args)

    def alternative(self, args):
        return Alternative(args)

    def reference(self, args):
        ref = args[0]
        try:
            return self.extras[ref]
        except KeyError:
            raise Exception("Unknown reference name %r" % (str(ref)))

    def special(self, args):
        child, specifier = args
        if '=' in specifier:
            name, value = specifier.split('=')

            # Try to convert the value to a bool, None or a float.
            if value in ['True', 'False']:
                value = bool(value)
            elif value == 'None':
                value = None
            else:
                try:
                    value = float(value)
                except ValueError:
                    # Conversion failed, value is just a string.
                    pass
        else:
            name, value = specifier, True

        if name in ['weight', 'w']:
            child.weight = float(value)
        elif name in ['test_special']:
            child.test_special = value
        else:
            raise ParseError("Unrecognized special specifier: {%s}" %
                             specifier)

        return child
