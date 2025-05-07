def flatten_keys(d, parent_key=''):
    keys = set()
    for k, v in d.items():
        full_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            keys |= flatten_keys(v, full_key)
        else:
            keys.add(full_key)
    return keys


def assert_required_keys(span, required_keys):
    flattened = flatten_keys(span)
    missing = [key for key in required_keys if key not in flattened]
    assert not missing, f"Missing required keys: {missing}"
