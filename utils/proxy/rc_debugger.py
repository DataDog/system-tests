import json
import base64
import copy
import os
import os.path
import hashlib


_CUR_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_CUR_DIR, "debugger/base_target.json"), "r", encoding="utf-8") as f:
    _BASE_TARGET = json.load(f)

with open(os.path.join(_CUR_DIR, "debugger/base_signed.json"), "r", encoding="utf-8") as f:
    _BASE_SIGNED = json.load(f)

with open(os.path.join(_CUR_DIR, "debugger/base_rcm.json"), "r", encoding="utf-8") as f:
    _BASE_RCM = json.load(f)


def create_rcm_probe_response(library, probe, version):
    def _json_to_base64(json_object):
        json_string = json.dumps(json_object).encode("utf-8")
        base64_string = base64.b64encode(json_string).decode("utf-8")
        return base64_string

    def _sha256(str):
        bytes = base64.b64decode(str)
        return hashlib.sha256(bytes).hexdigest()

    rcm = copy.deepcopy(_BASE_RCM)
    target = copy.deepcopy(_BASE_TARGET)
    signed = copy.deepcopy(_BASE_SIGNED)

    if probe is None:
        rcm["targets"] = _json_to_base64(signed)
    else:
        probe["language"] = library

        if probe["where"]["typeName"] == "ACTUAL_TYPE_NAME":
            if library == "dotnet":
                probe["where"]["typeName"] = "weblog.DebuggerController"
            elif library == "java":
                probe["where"]["typeName"] = "DebuggerController"
                probe["where"]["methodName"] = (
                    probe["where"]["methodName"][0].lower() + probe["where"]["methodName"][1:]
                )
        elif probe["where"]["sourceFile"] == "ACTUAL_SOURCE_FILE":
            if library == "dotnet":
                probe["where"]["sourceFile"] = "DebuggerController.cs"
            elif library == "java":
                probe["where"]["sourceFile"] = "DebuggerController.java"

        probe_64 = _json_to_base64(probe)
        path = "datadog/2/LIVE_DEBUGGING/" + probe["id"].split("-")[0] + "_" + probe["id"] + "/config"
        target[path] = target.pop(list(target.keys())[0])
        target[path]["hashes"]["sha256"] = _sha256(probe_64)
        target[path]["length"] = len(json.dumps(probe).encode("utf-8"))

        signed["signed"]["targets"] = target
        signed["signed"]["version"] = version

        rcm["targets"] = _json_to_base64(signed)
        rcm["target_files"][0]["path"] = path
        rcm["target_files"][0]["raw"] = probe_64
        rcm["client_configs"].append(path)

    return rcm
