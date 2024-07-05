import base64
import json
from black import format_str, FileMode
from utils._remote_config import RemoteConfigCommand


def from_payload(payload):
    targets = json.loads(base64.b64decode(payload["targets"]).decode("utf-8"))

    result = RemoteConfigCommand(version=targets["signed"]["version"], expires=targets["signed"]["expires"])

    # base64 -> bytes -> json -> dict
    configs = {t["path"]: t["raw"] for t in payload.get("target_files", [])}

    assert result.opaque_backend_state == targets["signed"]["custom"]["opaque_backend_state"]
    assert result.spec_version == targets["signed"]["spec_version"]
    assert result.expires == targets["signed"]["expires"], f"{result.expires} != {targets['signed']['expires']}"
    assert result.version == targets["signed"]["version"], f"{result.version} != {targets['signed']['version']}"
    # assert result.signatures == targets["signatures"], f"{result.signatures} != {targets['signatures']}"

    for config_name in payload.get("client_configs", []):
        target = targets["signed"]["targets"][config_name]
        raw_config = configs.get(config_name, None)

        config = result.add_client_config(config_name, raw_config, target["custom"]["v"])

        assert (
            config.config_file_version == target["custom"]["v"]
        ), f"{config.config_file_version} != {target['custom']['v']}"
        assert (
            config.raw_length == target["length"]
        ), f"Length mismatch for {config_name}: {len(config.raw_length)} != {target['length']}"
        assert (
            config.raw_sha256 == target["hashes"]["sha256"]
        ), f"SHA256 mismatch for {config_name}: {config.raw_sha256} != {target['hashes']['sha256']}"

    return result


def get_python_code(command: RemoteConfigCommand):
    kwargs = {"version": command.version}
    if command.expires != RemoteConfigCommand.expires:
        kwargs["expires"] = command.expires

    args = ",".join(f"{k}={v!r}" for k, v in kwargs.items())

    result = f"command = RemoteConfigCommand({args})"

    for config in command.targets:
        result += f"\ncommand.add_client_config{config!r}"

    return format_str(result, mode=FileMode(line_length=120))


def main(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        print("#" * 120)
        if item is None:
            print("None")
        else:
            command = from_payload(item)
            print(get_python_code(command))

        # print("-" * 120)
        # print(json.dumps(item, indent=2))
        # print("-" * 120)
        # print(json.dumps(command.to_payload(deserialized=True), indent=2))
    return


if __name__ == "__main__":
    main("utils/proxy/rc_mocked_responses_asm_nocache.json")
