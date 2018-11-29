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
        self.assert_found_text("elephant",
                               utils.TextQuery(full_phrase="elephant"),
                               "dog elephant tiger")
        self.assert_found_text("elephant ",
                               utils.TextQuery(full_phrase="elephant "),
                               "dog elephant tiger")
        self.assert_found_text("elephant.  ",
                               utils.TextQuery(full_phrase="elephant. "),
                               "dog elephant.  tiger")
        self.assert_found_text(" elephant",
                               utils.TextQuery(full_phrase=" elephant"),
                               "dog elephant tiger")
        self.assert_found_text("dog.",
                               utils.TextQuery(full_phrase="dog."),
                               "dog.elephant")
        self.assert_found_text("dog elephant tiger",
                               utils.TextQuery(start_phrase="dog", end_phrase="tiger"),
                               "dog elephant tiger")
        self.assert_found_text("sentence one.",
                               utils.TextQuery(start_phrase="sentence", end_phrase="."),
                               "sentence one. Sentence two.")
        self.assert_found_text(" elephant tiger",
                               utils.TextQuery(start_phrase="dog", end_phrase="tiger", start_after=True),
                               "doggy dog elephant tiger")
        self.assert_found_text("dog elephant tigers ",
                               utils.TextQuery(start_phrase="dog", end_phrase="tiger", end_before=True),
                               "dog elephant tigers tiger")
        self.assert_found_text("dog elephant",
                               utils.TextQuery(end_phrase="elephant"),
                               "dog elephant tiger",
                               cursor_offset=0)
        self.assert_found_text("elephant tiger",
                               utils.TextQuery(end_phrase="elephant"),
                               "dog elephant tiger",
                               cursor_offset=-1)
        self.assert_found_text("dog ",
                               utils.TextQuery(end_phrase="elephant", end_before=True),
                               "dog elephant tiger",
                               cursor_offset=0)
        self.assert_found_text(" tiger",
                               utils.TextQuery(end_phrase="elephant", end_after=True),
                               "dog elephant tiger",
                               cursor_offset=-1)


if __name__ == "__main__":
    unittest.main()
