class AccessibilityError(Exception):
    """Base class for checked exceptions."""


class UnsupportedSelectionError(AccessibilityError):
    """The built-in selection API is spotty when selecting across
    multiple objects. In Firefox you get results that look right, but the
    selection doesn't behave like a normal selection. Chrome simply does not
    support selections across multiple objects.
    """
