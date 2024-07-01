import base64
import sys
import json
import hashlib


def _json_to_base64(json_object):
    json_string = json.dumps(json_object).encode("utf-8")
    base64_string = base64.b64encode(json_string).decode("utf-8")
    return base64_string


def _sha256(value):
    return hashlib.sha256(base64.b64decode(value)).hexdigest()


def main(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    for payload in data:
        encoded_targets = payload["targets"]
        decoded_targets = json.loads(base64.b64decode(encoded_targets).decode("utf-8"))
        targets = decoded_targets["signed"]["targets"]
        for name, value in targets.items():
            print(json.dumps(name, indent=2))
            print(json.dumps(value, indent=2))
            print(len(json.dumps(value).encode("utf-8")))


if __name__ == "__main__":
    main(sys.argv[1])
