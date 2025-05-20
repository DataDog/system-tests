import json

from utils._context._scenarios import scenario_groups
from utils._context.core import context


def get_lang_configs():
    # ensure that any scneario using this method got scenario_groups.telemetry
    assert (
        scenario_groups.telemetry in context.scenario.scenario_groups
    ), f"Please add scenario group TELEMETRY to scenario {context.scenario.name}"

    lang_configs = {}
    for lang in ["dotnet", "go", "jvm", "nodejs", "php", "python", "ruby"]:
        lang_configs[lang] = load_telemetry_json(lang + "_config_rules")

    return lang_configs


def load_telemetry_json(filename: str):
    # ensure that any scneario using this method got scenario_groups.telemetry
    assert (
        scenario_groups.telemetry in context.scenario.scenario_groups
    ), f"Please add scenario group TELEMETRY to scenario {context.scenario.name}"

    with open(f"utils/telemetry/intake/static/{filename}.json", encoding="utf-8") as fh:
        return _lowercase_obj(json.load(fh))


def _lowercase_obj(obj: dict | list | str | float | bool | None):
    if isinstance(obj, dict):
        return {k.lower() if isinstance(k, str) else k: _lowercase_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_lowercase_obj(item) for item in obj]
    if isinstance(obj, str):
        return obj.lower()
    return obj
