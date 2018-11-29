import unittest

from dragonfly.a11y import utils


class AccessibilityTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def assert_found_text(self, expected, query, expanded_text, cursor_offset=0):
        if cursor_offset == -1:
            cursor_offset = len(expanded_text)
        result = utils._find_text(query, expanded_text, cursor_offset)
        if expected is None:
            self.assertIsNone(result)
        else:
            self.assertIsNotNone(result)
            self.assertEqual(expected, expanded_text[result[0]:result[1]])

    def test_find_text(self):
        # Simple phrase selection.
        self.assert_found_text("elephant",
                               utils.TextQuery(end_phrase="elephant"),
                               "dog elephant tiger")
        self.assert_found_text("elephant ",
                               utils.TextQuery(end_phrase="elephant "),
                               "dog elephant tiger")
        self.assert_found_text("elephant.  ",
                               utils.TextQuery(end_phrase="elephant. "),
                               "dog elephant.  tiger")
        self.assert_found_text(" elephant",
                               utils.TextQuery(end_phrase=" elephant"),
                               "dog elephant tiger")
        self.assert_found_text("dog.",
                               utils.TextQuery(end_phrase="dog."),
                               "dog.elephant")
        self.assert_found_text("dog",
                               utils.TextQuery(end_phrase="dog", end_relative_position=utils.Position.before, end_relative_phrase="elephant"),
                               "dog elephant tiger")
        self.assert_found_text("elephant",
                               utils.TextQuery(end_phrase="elephant", end_relative_position=utils.Position.after, end_relative_phrase="dog"),
                               "dog elephant tiger")
        self.assert_found_text(" ",
                               utils.TextQuery(end_phrase=" ", end_relative_position=utils.Position.before, end_relative_phrase="elephant"),
                               "dog elephant tiger")

        # Selecting a range.
        self.assert_found_text("dog elephant tiger",
                               utils.TextQuery(start_phrase="dog", through=True, end_phrase="tiger"),
                               "dog elephant tiger")
        self.assert_found_text("dog elephant tiger",
                               utils.TextQuery(start_phrase="dog", start_relative_position=utils.Position.before, start_relative_phrase="elephant", through=True, end_phrase="tiger"),
                               "dog elephant tiger")
        self.assert_found_text("sentence one.",
                               utils.TextQuery(start_phrase="sentence", through=True, end_phrase="."),
                               "sentence one. Sentence two.")
        self.assert_found_text(" one. Sentence two",
                               utils.TextQuery(start_phrase=" ", start_relative_position=utils.Position.before, start_relative_phrase="one", through=True, end_phrase="two"),
                               "sentence one. Sentence two.")
        self.assert_found_text(" elephant tiger",
                               utils.TextQuery(start_relative_position=utils.Position.after, start_relative_phrase="dog", through=True, end_phrase="tiger"),
                               "doggy dog elephant tiger")
        self.assert_found_text(" elephant tiger",
                               utils.TextQuery(start_relative_position=utils.Position.after, start_relative_phrase="doggy dog", through=True, end_phrase="tiger"),
                               "doggy dog elephant tiger")
        self.assert_found_text("dog elephant tigers ",
                               utils.TextQuery(start_phrase="dog", through=True, end_relative_position=utils.Position.before, end_relative_phrase="tiger"),
                               "dog elephant tigers tiger")

        # Selecting from the cursor position.
        self.assert_found_text("dog elephant",
                               utils.TextQuery(through=True, end_phrase="elephant"),
                               "dog elephant tiger",
                               cursor_offset=0)
        self.assert_found_text("elephant tiger",
                               utils.TextQuery(through=True, end_phrase="elephant"),
                               "dog elephant tiger",
                               cursor_offset=-1)
        self.assert_found_text("dog ",
                               utils.TextQuery(through=True, end_relative_position=utils.Position.before, end_relative_phrase="elephant"),
                               "dog elephant tiger",
                               cursor_offset=0)
        self.assert_found_text(" tiger",
                               utils.TextQuery(through=True, end_relative_position=utils.Position.after, end_relative_phrase="elephant"),
                               "dog elephant tiger",
                               cursor_offset=-1)


if __name__ == "__main__":
    unittest.main()
