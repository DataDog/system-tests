import argparse
import logging
import io
import os
from pathlib import Path
import sys
import tarfile
from typing import Any
import zipfile

import requests


logging.basicConfig(level=logging.DEBUG, format="%(levelname)-5s %(message)s")

logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_environ() -> dict[str, str]:
    environ = {**os.environ}

    try:
        with open(".env", encoding="utf-8") as f:
            lines = [line.replace("export ", "").strip().split("=") for line in f if line.strip()]
            environ = {**environ, **dict(lines)}
    except FileNotFoundError:
        pass

    return environ


def get_json(session: requests.Session, url: str, params: dict | None = None, timeout: int = 30) -> Any:  # noqa: ANN401
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def is_included(params: list[str], artifact_name: str) -> bool:
    return all(param in artifact_name for param in params)


def get_artifacts(session: requests.Session, repo_slug: str, workflow_file: str, run_id: int | None) -> list:
    if run_id is None:
        data = get_json(
            session,
            f"https://api.github.com/repos/{repo_slug}/actions/workflows/{workflow_file}/runs?",
            params={"per_page": 1},
        )
        workflow_run = data["workflow_runs"][0]
    else:
        workflow_run = get_json(session, f"https://api.github.com/repos/{repo_slug}/actions/runs/{run_id}")

    logging.info("Getting artifacts for run: %s", workflow_run["html_url"])

    artifacts = []

    for page in range(1, 10):
        items = get_json(session, workflow_run["artifacts_url"], params={"per_page": 100, "page": page})

        if len(items["artifacts"]) == 0:
            break

        artifacts.extend(items["artifacts"])

    return artifacts


def download_artifact(session: requests.Session, artifact: dict, output_dir: str) -> None:
    logging.info("Downloading artifact: %s", artifact["name"])
    response = session.get(artifact["archive_download_url"], timeout=60)
    response.raise_for_status()

    logging.info("Extracting artifact: %s", artifact["name"])
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(output_dir)

    for file in os.listdir(output_dir):
        if file.endswith(".tar.gz") and Path(os.path.join(output_dir, file)).is_file():
            with tarfile.open(os.path.join(output_dir, file), "r:gz") as t:
                t.extractall(output_dir, filter=lambda tar_info, _: tar_info)  # type: ignore[call-arg]


def main(
    run_id: int | None,
    params: list[str],
    repo_slug: str = "DataDog/system-tests-dashboard",
    workflow_file: str = "nightly.yml",
) -> None:
    environ = get_environ()

    with requests.Session() as session:
        session.headers.update({"Authorization": f"token {environ['GH_TOKEN']}"})

        artifacts = get_artifacts(session, repo_slug, workflow_file, run_id)
        artifacts = [artifact for artifact in artifacts if is_included(params, artifact["name"])]

        if len(artifacts) == 0:
            print("No artifacts found")
            sys.exit(1)

        if len(artifacts) > 1:
            print("Too many artifacts found:")
            for artifact in artifacts:
                print("", artifact["name"], artifact["archive_download_url"])

            sys.exit(1)

        download_artifact(session, artifacts[0], "tmp")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="grep-nightly-logs", description="Get logs artifact from nighty jobs")
    parser.add_argument("-r", "--run-id", type=int, help="The run id of the nightly job", required=False)
    parser.add_argument("params", type=str, nargs="+", help="Keys in artifact name")
    args = parser.parse_args()

    main(run_id=args.run_id, params=args.params)
