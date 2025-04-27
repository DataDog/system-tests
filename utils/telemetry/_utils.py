import json
from typing import Any

from utils._context._scenarios import ScenarioGroup
from utils._context.core import context


class _TelemetrySingleton:
    ALL_TELEMETRY_CONFIGS = None

    @staticmethod
    def get_all_telemetry_configs() -> dict[str, Any]:
        # ensure that any scenario using this method got ScenarioGroup.TELEMETRY
        assert (
            ScenarioGroup.TELEMETRY in context.scenario.scenario_groups
        ), f"Please add scenario group TELEMETRY to scenario {context.scenario.name}"

        if _TelemetrySingleton.ALL_TELEMETRY_CONFIGS is None:
            _TelemetrySingleton.ALL_TELEMETRY_CONFIGS = {
                "config_norm_rules": _load_telemetry_json("config_norm_rules"),
                "config_prefix_block_list": _load_telemetry_json("config_prefix_block_list"),
                "config_aggregation_list": _load_telemetry_json("config_aggregation_list"),
                "lang_configs": _load_get_lang_configs(),
            }

        return _TelemetrySingleton.ALL_TELEMETRY_CONFIGS


def get_lang_configs():
    return _TelemetrySingleton.get_all_telemetry_configs()["lang_configs"]


def _load_get_lang_configs():
    lang_configs = {}
    for lang in ["dotnet", "go", "jvm", "nodejs", "php", "python", "ruby"]:
        lang_configs[lang] = _load_telemetry_json(lang + "_config_rules")

    return lang_configs


def get_config_norm_rules():
    return _TelemetrySingleton.get_all_telemetry_configs()["config_norm_rules"]


def get_config_prefix_block_list():
    return _TelemetrySingleton.get_all_telemetry_configs()["config_prefix_block_list"]


def get_config_aggregation_list():
    return _TelemetrySingleton.get_all_telemetry_configs()["config_aggregation_list"]


def _load_telemetry_json(filename: str):
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
