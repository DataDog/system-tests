import json
import os.path

_CUR_DIR = os.path.dirname(os.path.abspath(__file__))

MOCKED_RESPONSES = {}

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_live_debugging.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["LIVE_DEBUGGING"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm_features.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM_FEATURES"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm_activate_only.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM_ACTIVATE_ONLY"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm_dd.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM_DD"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm_data.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM_DATA"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm_data_ip_blocking_maxed.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM_DATA_IP_BLOCKING_MAXED"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_live_debugging_nocache.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["LIVE_DEBUGGING_NO_CACHE"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm_features_nocache.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM_FEATURES_NO_CACHE"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm_dd_nocache.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM_DD_NO_CACHE"] = json.load(f)

with open(os.path.join(_CUR_DIR, "rc_mocked_responses_asm_nocache.json"), encoding="utf-8") as f:
    MOCKED_RESPONSES["ASM_NO_CACHE"] = json.load(f)
