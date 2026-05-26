#!/usr/bin/env python3
"""
Merge per-language SSI pipeline YAMLs into a single generated-ssi-pipeline.yml.

Works the same way as build_pipeline.py does for end-to-end scenarios:
compute_pipeline generates one YAML per language, this script combines them into
a single artifact consumed by a single run_ssi_pipeline trigger job.

Usage: build_ssi_pipeline.py library1 library2 ...
"""

import sys
from pathlib import Path

import yaml

_PIPELINE_KEYS = {"workflow", "include", "variables", "stages"}


def _merge(libraries: list[str]) -> dict:
    merged: dict = {
        "workflow": {"name": "SSI"},
        "include": [],
        "variables": {},
        "stages": [],
    }
    seen_includes: set[str] = set()

    for lib in libraries:
        path = Path(f"{lib}_ssi_gitlab_pipeline.yml")
        if not path.exists():
            continue
        data: dict = yaml.safe_load(path.read_text()) or {}

        # Deduplicate includes (all languages share the same remote template)
        for item in data.get("include", []):
            key = yaml.dump(item, default_flow_style=True)
            if key not in seen_includes:
                merged["include"].append(item)
                seen_includes.add(key)

        # Variables are identical across languages — first one wins
        for k, v in data.get("variables", {}).items():
            merged["variables"].setdefault(k, v)

        # Prefix stage names with the library to avoid cross-language conflicts
        stage_map: dict[str, str] = {}
        for stage in data.get("stages", []):
            new_stage = f"{lib.upper()}_{stage}"
            stage_map[stage] = new_stage
            if new_stage not in merged["stages"]:
                merged["stages"].append(new_stage)

        for key, value in data.items():
            if key in _PIPELINE_KEYS:
                continue
            if key.startswith("."):
                # Hidden/base job — shared across languages, include only once
                merged.setdefault(key, value)
            else:
                # Regular job — prefix with library to guarantee uniqueness
                job = dict(value)
                if "stage" in job:
                    job["stage"] = stage_map.get(job["stage"], job["stage"])
                merged[f"{lib}_{key}"] = job

    return merged


if __name__ == "__main__":
    libraries = sys.argv[1:]
    if not libraries:
        print("Usage: build_ssi_pipeline.py lib1 lib2 ...", file=sys.stderr)
        sys.exit(1)

    output = yaml.dump(_merge(libraries), sort_keys=False, default_flow_style=False)
    Path("generated-ssi-pipeline.yml").write_text(output)
    print("Generated: generated-ssi-pipeline.yml")
