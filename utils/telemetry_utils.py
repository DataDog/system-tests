import glob
import json
import os
from pathlib import Path
from jsonschema.validators import Draft7Validator, RefResolver
import typing

ROOT_PROJECT = Path(__file__).parent.parent


class TelemetryV2Validator:
    def __init__(self) -> None:
        schema_store = {}

        schema_dir = os.path.join(ROOT_PROJECT, "utils/interfaces/schemas/miscs/telemetry")
        for schema_path in glob.iglob("**/*.json", root_dir=schema_dir, recursive=True):
            with open(schema_dir + "/" + schema_path, "r") as f:
                schema = json.load(f)
                schema_store[schema["$id"]] = schema

        main_schema = None
        with open(schema_dir + "/v2/telemetry_request.json", "r") as f:
            main_schema = json.load(f)

        self.resolver = RefResolver.from_schema(main_schema, store=schema_store)
        self.validator = Draft7Validator(
            schema=main_schema,
            resolver=self.resolver,
        )

    def validate(self, data: str) -> bool:
        try:
            self.validator.validate(data)
            return True
        except Exception:
            return False

    def get_errors(self, data: str) -> list[dict[str, typing.Any]]:
        errors = []
        for e in sorted(self.validator.iter_errors(data), key=lambda e: e.path):
            errors.append({"reason": e.message, "location": e.json_path, "json": e.instance})
        return errors


class TelemetryUtils:
    test_loaded_dependencies = {
        "dotnet": {"NodaTime": False},
        "nodejs": {"glob": False},
        "java": {"org.apache.httpcomponents:httpclient": False},
        "ruby": {"bundler": False},
        "python": {"requests": False},
    }

    @staticmethod
    def get_loaded_dependency(library) -> dict[str, bool]:
        return TelemetryUtils.test_loaded_dependencies[library]

    @staticmethod
    def get_dd_appsec_sca_enabled_str(library) -> str:
        result = "DD_APPSEC_SCA_ENABLED"
        if library == "java":
            result = "appsec_sca_enabled"
        elif library == "nodejs":
            result = "appsec.sca.enabled"
        elif library in ("php", "ruby"):
            result = "appsec.sca_enabled"
        return result
