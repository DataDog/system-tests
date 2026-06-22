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


def render_library(
    library: str,
    params: dict,
    *,
    skip_header: bool,
    stage: str,
    ci_image: str,
    ref: str,
    push_to_test_optimization: bool,
    docker_auth: bool,
    binaries_artifact_path: str,
    binaries_artifacts: str,
) -> str:
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
    # Build the full list of artifact jobs for cross-pipeline downloads.
    # If binaries_artifacts is provided, use it; otherwise fall back to the single job.
    if binaries_artifacts:
        binaries_artifacts_list = [j.strip() for j in binaries_artifacts.split(";") if j.strip()]
    elif binaries_artifact:
        binaries_artifacts_list = [binaries_artifact]
    else:
        binaries_artifacts_list = []
    return _template.render(
        scenario_pairs=scenario_pairs,
        stage=stage,
        library=library,
        weblog_variants=weblog_variants,
        binaries_artifact=binaries_artifact,
        binaries_artifacts_list=binaries_artifacts_list,
        binaries_artifact_path=binaries_artifact_path,
        parametric=parametric,
        ci_image=ci_image,
        ref=ref,
        push_to_test_optimization=push_to_test_optimization,
        skip_header=skip_header,
        docker_auth_enabled=docker_auth,
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
    docker_auth: bool = False,
    binaries_artifact_path: str = "",
    binaries_artifacts: str = "",
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
            parts.append(
                render_library(
                    library,
                    params,
                    skip_header=(lib_idx > 0),
                    stage=stage,
                    ci_image=ci_image,
                    ref=ref,
                    push_to_test_optimization=push_to_test_optimization,
                    docker_auth=docker_auth,
                    binaries_artifact_path=binaries_artifact_path,
                    binaries_artifacts=binaries_artifacts,
                )
            )

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
    parser.add_argument("--docker-auth", default="false", help="Whether to authenticate calls to docker hub")
    parser.add_argument(
        "--binaries-artifact-path",
        default="",
        help="Path (relative to CI_PROJECT_DIR) of the binaries_artifact contents, copied into binaries/",
    )
    parser.add_argument(
        "--binaries-artifacts",
        default="",
        help="Semicolon-separated list of upstream jobs to download artifacts from in the child pipeline "
        "(';' not ',' because job names may contain commas, e.g. parallel matrix names; "
        "falls back to the single binaries_artifact from params if empty)",
    )

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
        docker_auth=args.docker_auth == "true",
        binaries_artifact_path=args.binaries_artifact_path,
        binaries_artifacts=args.binaries_artifacts,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
