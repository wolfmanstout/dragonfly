import re

def _move_cursor_in_text(accessible_text, phrase, before=False):
    # print "Moving cursor. Text: %s\nPhrase: %s" % (accessible_text.to_string(), phrase)
    regex = r"[^a-z]*".join(re.escape(word) for word in re.split(r"[^a-z]+", phrase))
    matches = re.finditer(regex, accessible_text.expanded_text, re.IGNORECASE)
    indices = [match.start() if before else match.end()
               for match in matches]
    # print "Matches: %s" % indices
    if len(indices) > 0:
        # TODO Choose index nearest to cursor location.
        accessible_text.set_cursor(indices[0])
    else:
        print "Not found: %s" % phrase

def move_cursor(controller, phrase, before=False):
    focused = controller.get_focused()
    if focused:
        focused.manipulate_text(lambda accessible_text: _move_cursor_in_text(accessible_text, phrase, before))
    else:
        print "Nothing is focused."
