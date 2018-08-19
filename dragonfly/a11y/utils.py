import re

def move_cursor(controller, phrase, before=False):
    print "Moving cursor %s phrase: %s" % ("before" if before else "after", phrase)
    def closure(context):
        if not context.focused:
            print "Nothing is focused."
            return
        accessible_text = context.focused.as_text()
        regex = r"[^A-Za-z]*".join(re.escape(word) for word in re.split(r"[^A-Za-z]+", phrase))
        matches = re.finditer(regex, accessible_text.expanded_text, re.IGNORECASE)
        indices = [match.start() if before else match.end()
                   for match in matches]
        if len(indices) > 0:
            # TODO Choose index nearest to cursor location.
            accessible_text.set_cursor(indices[0])
            print "Moved cursor"
        else:
            print "Not found: %s" % phrase
    controller.run_sync(closure)

def get_text_selection_points(controller, phrase):
    print "Getting text selection points: %s" % phrase
    def closure(context):
        if not context.focused:
            print "Nothing is focused."
            return
        accessible_text = context.focused.as_text()
        regex = r"[^A-Za-z]*".join(re.escape(word) for word in re.split(r"[^A-Za-z]+", phrase))
        matches = re.finditer(regex, accessible_text.expanded_text, re.IGNORECASE)
        ranges = [(match.start(), match.end())
                  for match in matches]
        if len(ranges) > 0:
            # TODO Choose selection nearest to cursor location.
            selection = ranges[0]
            start_box = accessible_text.get_bounding_box(selection[0])
            end_box = accessible_text.get_bounding_box(selection[1] - 1)
            return ((start_box.x, start_box.y + start_box.height / 2),
                    (end_box.x + end_box.width, end_box.y + end_box.height / 2))
        else:
            print "Not found: %s" % phrase
    return controller.run_sync(closure)
    

def is_editable_focused(controller):
    def closure(context):
        return context.focused and context.focused.is_editable()
    return controller.run_sync(closure)
