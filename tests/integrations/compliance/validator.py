def _get_nested(d: dict, dotted_key: str):
    keys = dotted_key.split(".")
    if len(keys) > 1 and keys[0] in ("meta", "metrics"):
        keys = [keys[0]] + [".".join(keys[1:])]
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return None
    return d


def assert_required_keys(span: dict, schema: dict) -> tuple[list[str], list[str]]:
    required = schema["required_span_attributes"]
    deprecated_aliases = schema.get("deprecated_aliases", {})

    mandatory_keys = required["mandatory"]
    # best_effort_keys = required.get("best_effort", [])

    missing_keys = []
    deprecated_used = []

    for key in mandatory_keys:
        if _get_nested(span, key) is not None:
            continue

        fallback_keys = deprecated_aliases.get(key, [])
        for fallback in fallback_keys:
            if _get_nested(span, fallback) is not None:
                deprecated_used.append(fallback)
                break
        else:
            missing_keys.append(key)

    # for key in best_effort_keys:
    #    if _get_nested(span, key) is None:
    #        print(f"[BEST-EFFORT] Optional but recommended key not found: {key}")

    return missing_keys, deprecated_used
