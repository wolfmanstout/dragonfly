import re
import enum

# TODO Change prints into log statements


class TextQuery(object):
    """A query to match a range of text."""
    
    def __init__(self,
                 full_phrase="",
                 start_phrase="",
                 end_phrase="",
                 start_before=False,
                 start_after=False,
                 end_before=False,
                 end_after=False):
        if full_phrase and (start_phrase or end_phrase):
            raise ValueError("Cannot specify both full phrase and start or end")
        if start_phrase and not end_phrase:
            raise ValueError("Cannot specify only start phrase")
        if start_before and start_after or end_before and end_after:
            raise ValueError("Inconsistent before/after values")

        self.full_phrase = full_phrase
        self.start_phrase = start_phrase
        self.end_phrase = end_phrase
        self.start_before = start_before
        self.start_after = start_after
        self.end_before = end_before
        self.end_after = end_after

    def __str__(self):
        return str(dict([(k, v) for (k, v) in self.__dict__.items() if v]))
        

class Position(enum.Enum):
    """The cursor position relative to a range of text."""
    
    start = 1
    end = 2


class TextInfo(object):
    """Information about a range of text."""
    
    def __init__(self, start, end, text, start_coordinates=None, end_coordinates=None):
        self.start = start
        self.end = end
        self.text = text
        self.start_coordinates = start_coordinates
        self.end_coordinates = end_coordinates


def _phrase_to_regex(phrase, before=False, after=False):
    assert not (before and after)
    
    # Treat whitespace as meaning anything other than alphanumeric characters.
    regex = r"[^A-Za-z0-9]+".join(re.escape(word) for word in phrase.split())
    # Only match at boundaries of alphanumeric sequences.
    regex = r"(?<![A-Za-z0-9])" + regex + r"(?![A-Za-z0-9])"
    if before:
        regex = r"(?=" + regex + r")"
    if after:
        regex = r"(?<=" + regex + r")"
    return regex

    
def _find_text(query, expanded_text, cursor_offset):
    # Convert query to regex.
    start_with_cursor = query.end_phrase and not query.start_phrase
    if query.full_phrase:
        regex = _phrase_to_regex(query.full_phrase)
    elif start_with_cursor:
        regex = _phrase_to_regex(query.end_phrase, query.end_before, query.end_after)
    else:
        assert query.start_phrase and query.end_phrase
        regex = (_phrase_to_regex(query.start_phrase, query.start_before, query.start_after) +
                 r".*?" +
                 _phrase_to_regex(query.end_phrase, query.end_before, query.end_after))

    # Find all matches.
    matches = re.finditer(regex, expanded_text, re.IGNORECASE)
    ranges = [(match.start(), match.end()) for match in matches]
    if not ranges:
        print "Not found: %s" % query
        return None
    if cursor_offset is None:
        print "Warning: cursor not found."
        if start_with_cursor:
            print "Cannot get range without cursor."
            return None
        else:
            # Pick arbitrary match (the first one).
            return ranges[0]
    else:
        # Find nearest match.
        range = min(ranges, key=lambda x: abs((x[0] + x[1]) / 2 - cursor_offset))
        if start_with_cursor:
            if range[0] < cursor_offset:
                return (range[0], cursor_offset)
            else:
                return (cursor_offset, range[1])
        else:
            return range


def _get_focused_text(context):
    if not context.focused:
        print "Nothing is focused."
        return None
    focused_text = context.focused.as_text()
    if not focused_text:
        print "Focused element is not text."
        return None
    return focused_text


def get_cursor_offset(controller):
    def closure(context):
        focused_text = _get_focused_text(context)
        if not focused_text:
            return None
        return focused_text.cursor
    return controller.run_sync(closure)


def set_cursor_offset(controller, offset):
    def closure(context):
        focused_text = _get_focused_text(context)
        if not focused_text:
            return None
        focused_text.set_cursor(offset)
    controller.run_sync(closure)


def get_text_info(controller, query):
    print "Getting text info: %s" % query
    def closure(context):
        focused_text = _get_focused_text(context)
        if not focused_text:
            return None
        nearest = _find_text(query, focused_text.expanded_text, focused_text.cursor)
        if not nearest:
            return None
        text_info = TextInfo(nearest[0], nearest[1],
                             focused_text.expanded_text[nearest[0]:nearest[1]])
        start_box = focused_text.get_bounding_box(nearest[0])
        end_box = focused_text.get_bounding_box(nearest[1] - 1)
        # Ignore offscreen coordinates. Google Docs returns these, and we handle
        # it here to avoid further trouble.
        if start_box.x < 0 or start_box.y < 0 or end_box.x < 0 or end_box.y < 0:
            print "Text selection points were offscreen, ignoring."
        else:
            text_info.start_coordinates = start_box.x, start_box.y + start_box.height / 2
            text_info.end_coordinates = end_box.x + end_box.width, end_box.y + end_box.height / 2
        return text_info
    return controller.run_sync(closure)


def move_cursor(controller, query, position):
    """Moves the cursor before or after the provided phrase."""

    print "Moving cursor %s phrase: %s" % (position.name, query)
    def closure(context):
        focused_text = _get_focused_text(context)
        if not focused_text:
            return False
        nearest = _find_text(query, focused_text.expanded_text, focused_text.cursor)
        if not nearest:
            return False
        focused_text.set_cursor(nearest[0] if position is Position.start else nearest[1])
        print "Moved cursor"
        return True
    return controller.run_sync(closure)


def select_text(controller, query):
    print "Selecting text: %s" % query
    def closure(context):
        focused_text = _get_focused_text(context)
        if not focused_text:
            return False
        nearest = _find_text(query, focused_text.expanded_text, focused_text.cursor)
        if not nearest:
            return False
        focused_text.select_range(*nearest)
        print "Selected text"
        return True
    return controller.run_sync(closure)


def is_editable_focused(controller):
    """Returns true if an editable object is focused."""

    def closure(context):
        return context.focused and context.focused.is_editable()
    return controller.run_sync(closure)
