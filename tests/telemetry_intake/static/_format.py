import os
import json


def get_dot_notation_keys(obj, parent_key="", result=None):
    if result is None:
        result = []

    for k, v in obj.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            get_dot_notation_keys(v, new_key, result)
        else:
            result.append(new_key)

    return result


def validate_duplicate_keys(filename, data):
    """
    In the telemetry-intake service we convert all keys to lowercase [here][1].
    When this service receives a telemetry payload the configuration name is
    also converted to lowercase [here][2] and then used to access the
    normalized value. Because of this logic configuration names are not
    case-sensitive. However, json normalization file can contain keys with the
    same characters but different casing (ex: {"MOON": "ears", "moon": "e"} are
    valid entries in the config rules) but only one of these mappings will be
    used.

    [1]: https://github.com/DataDog/dd-go/blob/3195ddf0029639dec626c40aa8013ba7b69ae011/trace/apps/tracer-telemetry-intake/telemetry-payload/config.go#L151C3-L151C12
    [2]: https://github.com/DataDog/dd-go/blob/3195ddf0029639dec626c40aa8013ba7b69ae011/trace/apps/tracer-telemetry-intake/telemetry-payload/config.go#L220
    """
    keys = data if isinstance(data, list) else list(get_dot_notation_keys(data))
    lowercase_keys = [key.lower() for key in keys]
    duplicates = []
    seen = set()
    for key in lowercase_keys:
        if key in seen:
            duplicates.append(key)
        seen.add(key)

    if len(duplicates) > 0:
        print(f"Duplicate keys detected: {filename} - {duplicates}")


def validate(filename, data):
    validate_duplicate_keys(filename, data)


def main():
    config_dir = os.path.dirname(os.path.abspath(__file__))

    for filename in sorted(os.listdir(config_dir)):
        if filename.endswith(".json"):
            filepath = os.path.join(config_dir, filename)
            try:
                with open(filepath, "r") as file:
                    data = json.load(file)

                validate(filename, data)

                with open(filepath, "w") as file:
                    json.dump(data, file, indent=4, sort_keys=True)
            except json.JSONDecodeError:
                print(f"JSON invalid: {filename}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")


if __name__ == "__main__":
    """
    Automatically sorts and formats the files, ensuring a consistent formatting
    for each file.

    Usage: 
    python ./trace/apps/tracer-telemetry-intake/telemetry-payload/static/_format.py 

    This is not required as part of auto formatting or CI (yet), but should be
    run by contributors when updating config rules or periodically, if previous
    config changes were missed.
    """

    main()
