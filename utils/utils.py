# lazy load handler
_missing = object()


def is_iter(obj):
    """
    Checks if an object behaves iterably.
    Args:
        obj (any): Entity to check for iterability.
    Returns:
        is_iterable (bool): If `obj` is iterable or not.
    Notes:
        Strings are *not* accepted as iterable (although they are
        actually iterable), since string iterations are usually not
        what we want to do with a string.
    """
    if isinstance(obj, (str, bytes)):
        return False

    try:
        return iter(obj) and True
    except TypeError:
        return False


def make_iter(obj):
    """
    Makes sure that the object is always iterable.
    Args:
        obj (any): Object to make iterable.
    Returns:
        iterable (list or iterable): The same object
            passed-through or made iterable.
    """
    return not is_iter(obj) and [obj] or obj


class lazy_property(object):
    """
    Delays loading of property until first access. Credit goes to the
    Implementation in the werkzeug suite:
    http://werkzeug.pocoo.org/docs/utils/#werkzeug.utils.cached_property
    This should be used as a decorator in a class and in Evennia is
    mainly used to lazy-load handlers:
        ```python
        @lazy_property
        def attributes(self):
            return AttributeHandler(self)
        ```
    Once initialized, the `AttributeHandler` will be available as a
    property "attributes" on the object.
    """
    def __init__(self, func, name=None, doc=None):
        """Store all properties for now"""
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, type=None):
        """Triggers initialization"""
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, _missing)
        if value is _missing:
            value = self.func(obj)
        obj.__dict__[self.__name__] = value
        return value