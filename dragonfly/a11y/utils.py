import re

def get_cursor_offset(controller):
    def closure(context):
        if not context.focused:
            print "Nothing is focused."
            return
        return context.focused.as_text().cursor
    return controller.run_sync(closure)
    

def set_cursor_offset(controller, offset):
    def closure(context):
        if not context.focused:
            print "Nothing is focused."
            return
        context.focused.as_text().set_cursor(offset)
    controller.run_sync(closure)
    

def move_cursor(controller, phrase, before=False):
    """Moves the cursor before or after the provided phrase."""

    print "Moving cursor %s phrase: %s" % ("before" if before else "after", phrase)
    def closure(context):
        if not context.focused:
            print "Nothing is focused."
            return
        accessible_text = context.focused.as_text()
        regex = r"[^A-Za-z]*".join(re.escape(word) if word != "through" else ".*?"
                                   for word in re.split(r"[^A-Za-z]+", phrase))
        matches = re.finditer(regex, accessible_text.expanded_text, re.IGNORECASE)
        indices = [match.start() if before else match.end()
                   for match in matches]
        if len(indices) > 0:
            nearest = min(indices, key=((lambda x: abs(x - accessible_text.cursor))
                                        if accessible_text.cursor is not None else None))
            accessible_text.set_cursor(nearest)
            print "Moved cursor"
        else:
            print "Not found: %s" % phrase
    controller.run_sync(closure)


def get_text_selection_points(controller, phrase):
    """Gets the starting and ending selection points needed to select the provided
    phrase. This uses mouse-based selection instead of the built-in selection
    system because support for this system is spotty when selecting across
    multiple objects. In Firefox you get results that look right, but the
    selection doesn't behave like a normal selection. Chrome simply does not
    support selections across multiple objects."""

    print "Getting text selection points: %s" % phrase
    def closure(context):
        if not context.focused:
            print "Nothing is focused."
            return
        accessible_text = context.focused.as_text()
        regex = r"[^A-Za-z]*".join(re.escape(word) if word != "through" else ".*?"
                                   for word in re.split(r"[^A-Za-z]+", phrase))
        matches = re.finditer(regex, accessible_text.expanded_text, re.IGNORECASE)
        ranges = [(match.start(), match.end())
                  for match in matches]
        if len(ranges) > 0:
            nearest = min(ranges, key=((lambda x: abs((x[0] + x[1]) / 2 - accessible_text.cursor))
                                       if accessible_text.cursor is not None else None))
            start_box = accessible_text.get_bounding_box(nearest[0])
            end_box = accessible_text.get_bounding_box(nearest[1] - 1)
            return ((start_box.x, start_box.y + start_box.height / 2),
                    (end_box.x + end_box.width, end_box.y + end_box.height / 2))
        else:
            print "Not found: %s" % phrase
    return controller.run_sync(closure)


def is_editable_focused(controller):
    """Returns true if an editable object is focused."""

    def closure(context):
        return context.focused and context.focused.is_editable()
    return controller.run_sync(closure)
