from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent), autoescape=select_autoescape())
_template = _env.get_template("system-tests.yml.j2")


def noop_stub(stage: str) -> str:
    """Return a minimal valid GitLab pipeline YAML for an empty chunk."""
    return f"""workflow:
  name: "System-tests end to end (empty chunk)"
stages:
  - {stage}
noop:
  stage: {stage}
  image: registry.ddbuild.io/images/mirror/alpine:latest
  tags:
    - arch:amd64
  script:
    - echo "no libraries assigned to this chunk"
"""


def render_library(library: str, params: dict, *, skip_header: bool, stage: str, ci_image: str, ref: str, push_to_test_optimization: bool) -> str:  # noqa: E501
    parallel_weblogs = params.get("endtoend_defs", {}).get("parallel_weblogs", [])
    parallel_jobs = params.get("endtoend_defs", {}).get("parallel_jobs", [])
    weblog_variants = [w["name"] for w in parallel_weblogs]
    scenario_pairs = [
        (job["weblog"], scenario, job.get("weblog_build_required", True))
        for job in parallel_jobs
        for scenario in job.get("scenarios", [])
    ]
    binaries_artifact = params["miscs"]["binaries_artifact"]
    parametric = params["parametric"]
    return _template.render(
        scenario_pairs=scenario_pairs,
        stage=stage,
        library=library,
        weblog_variants=weblog_variants,
        binaries_artifact=binaries_artifact,
        parametric=parametric,
        ci_image=ci_image,
        ref=ref,
        push_to_test_optimization=push_to_test_optimization,
        skip_header=skip_header,
    )


def build(
    libraries: list[str],
    params_dir: Path,
    output_dir: Path,
    *,
    stage: str,
    ci_image: str,
    ref: str = "",
    push_to_test_optimization: bool = False,
    chunks: int = 3,
) -> None:
    """Render pipeline chunk files into *output_dir*, one per chunk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Assign libraries to chunks via simple round-robin
    chunk_libraries: dict[int, list[str]] = {i: [] for i in range(chunks)}
    for idx, library in enumerate(libraries):
        chunk_libraries[idx % chunks].append(library)

    # Render and write all chunks; empty chunks get a noop stub so trigger jobs
    # always have a valid pipeline file — dotenv vars are not available in rules:
    # at pipeline-creation time (gitlab-org/gitlab#235812).
    for chunk_idx, chunk_libs in chunk_libraries.items():
        chunk_file = output_dir / f"generated-pipeline-chunk-{chunk_idx}.yml"

        if not chunk_libs:
            chunk_file.write_text(noop_stub(stage))
            continue

        parts = []
        for lib_idx, library in enumerate(chunk_libs):
            params_file = params_dir / f"params_{library}.json"
            if not params_file.exists():
                print(f"ERROR: params file not found for library '{library}': {params_file}", file=sys.stderr)  # noqa: T201
                sys.exit(1)
            with open(params_file) as f:
                params = json.load(f)
            parts.append(render_library(library, params, skip_header=(lib_idx > 0), stage=stage, ci_image=ci_image, ref=ref, push_to_test_optimization=push_to_test_optimization))  # noqa: E501

        chunk_file.write_text("\n".join(parts))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, help="GitLab CI stage for the generated jobs")
    parser.add_argument("--libraries", required=True, help="Space-separated list of library names")
    parser.add_argument("--params-dir", required=True, help="Directory containing params_<lib>.json files")
    parser.add_argument("--ci-image", required=True, help="Full CI image reference for generated jobs")
    parser.add_argument("--ref", default="", help="system-tests ref to clone when called from another repository")
    parser.add_argument("--push-to-test-optimization", default="false", help="Generate the push_test_optimization job")
    parser.add_argument("--output-dir", required=True, help="Output directory for generated-pipeline-chunk-N.yml files")
    parser.add_argument("--chunks", type=int, default=3, help="Number of pipeline chunks (default: 3)")

    args = parser.parse_args(argv)

    libraries = args.libraries.split()
    if not libraries:
        print("No libraries specified, nothing to generate.", file=sys.stderr)  # noqa: T201
        return 0

    build(
        libraries=libraries,
        params_dir=Path(args.params_dir),
        output_dir=Path(args.output_dir),
        stage=args.stage,
        ci_image=args.ci_image,
        ref=args.ref,
        push_to_test_optimization=args.push_to_test_optimization == "true",
        chunks=args.chunks,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
