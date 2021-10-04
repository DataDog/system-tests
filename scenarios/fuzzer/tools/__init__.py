from ._data import _Data

data = _Data()


def apply_method(obj, key_callback, value_callback):
    """
    Recursyvly apply methods on a JSON-like object
    """
    if obj is None or isinstance(obj, (str, float, int, bool)):
        return value_callback(obj)

    if isinstance(obj, list):
        return [apply_method(value, key_callback, value_callback) for value in obj]

    if isinstance(obj, dict):
        return {key_callback(key): apply_method(value, key_callback, value_callback) for key, value in obj.items()}

    raise TypeError("Unexpcted type : " + str(type(obj)))
