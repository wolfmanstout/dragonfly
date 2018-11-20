import re
import enum

def _get_focused_text(context):
    if not context.focused:
        print "Nothing is focused."
        return None
    focused_text = context.focused.as_text()
    if not focused_text:
        print "Focused element is not text."
        return None
    return focused_text


def _get_nearest_range(focused_text, phrase):
    until = phrase.startswith("until ")
    if until:
        phrase = phrase[len("until "):]
    regex = r"\b" + (r"[^A-Za-z]+".join(re.escape(word) if word != "through" else ".*?"
                                        for word in re.split(r"[^A-Za-z]+", phrase))) + r"\b"
    matches = re.finditer(regex, focused_text.expanded_text, re.IGNORECASE)
    ranges = [(match.start(), match.end()) for match in matches]
    if not ranges:
        print "Not found: %s" % phrase
        return None
    if focused_text.cursor is None:
        print "Warning: cursor not found."
        if until:
            print "Cannot get range without cursor."
            return None
        else:
            return min(ranges)
    else:
        range = min(ranges, key=lambda x: abs((x[0] + x[1]) / 2 - focused_text.cursor))
        if until:
            if range[0] < focused_text.cursor:
                return (range[0], focused_text.cursor)
            else:
                return (focused_text.cursor, range[1])
        else:
            return range


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


class TextInfo(object):
    def __init__(self, start, end, text, start_coordinates=None, end_coordinates=None):
        self.start = start
        self.end = end
        self.text = text
        self.start_coordinates = start_coordinates
        self.end_coordinates = end_coordinates


def get_text_info(controller, phrase):
    print "Getting text info: %s" % phrase
    def closure(context):
        focused_text = _get_focused_text(context)
        if not focused_text:
            return None
        nearest = _get_nearest_range(focused_text, phrase)
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


class Position(enum.Enum):
    start = 1
    end = 2


def move_cursor(controller, phrase, position):
    """Moves the cursor before or after the provided phrase."""

    print "Moving cursor %s phrase: %s" % (position.name, phrase)
    def closure(context):
        focused_text = _get_focused_text(context)
        if not focused_text:
            return False
        nearest = _get_nearest_range(focused_text, phrase)
        if not nearest:
            return False
        focused_text.set_cursor(nearest[0] if position is Position.start else nearest[1])
        print "Moved cursor"
        return True
    return controller.run_sync(closure)


def select_text(controller, phrase):
    print "Selecting text: %s" % phrase
    def closure(context):
        focused_text = _get_focused_text(context)
        if not focused_text:
            return False
        nearest = _get_nearest_range(focused_text, phrase)
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
