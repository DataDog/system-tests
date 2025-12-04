import requests
import zipfile
import os
from tqdm import tqdm
from .types import Context
import json


def pull_artifact(url: str, token: str, path_root: str, path_data_root: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "python-requests",
    }

    # Get workflow runs
    with requests.get(url, headers=headers, timeout=60) as resp_runs:
        resp_runs.raise_for_status()
        runs_data = resp_runs.json()

    download_url = None
    page = 0
    print(f"CI workflow URL: {runs_data['workflow_runs'][0]['html_url']}")
    while not download_url:
        page += 1
        artifacts_url = runs_data["workflow_runs"][0]["artifacts_url"] + f"?page={page}"
        with requests.get(artifacts_url, headers=headers, timeout=60) as resp_artifacts:
            resp_artifacts.raise_for_status()
            artifacts_data = resp_artifacts.json()

        # Download the first artifact
        for artifact in artifacts_data["artifacts"]:
            if artifact["name"] == "test-report":
                download_url = artifact["archive_download_url"]

        # If we've checked all pages and found no test-report artifact, error
        if not download_url and len(artifacts_data["artifacts"]) == 0:
            raise RuntimeError("test-report not found in the last nightly run")

    with requests.get(download_url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("content-length", 0))

        with (
            open(f"{path_root}/data.zip", "wb") as f,
            tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading artifact") as pbar,
        ):
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    # Extract the downloaded zip file
    with zipfile.ZipFile(f"{path_root}/data.zip") as z:
        z.extractall(path_data_root)


def parse_artifact_data(path_data_opt: str, libraries: list[str]) -> dict[Context, list[str]]:
    test_data: dict[Context, list[str]] = {}

    for directory in os.listdir(path_data_opt):
        if "_dev_" in directory:
            continue

        for scenario in os.listdir(f"{path_data_opt}/{directory}"):
            try:
                with open(f"{path_data_opt}/{directory}/{scenario}/report.json", encoding="utf-8") as file:
                    scenario_data = json.load(file)
            except FileNotFoundError:
                continue

            context = Context.create(
                scenario_data["context"].get("library_name"),
                scenario_data["context"].get("library"),
                scenario_data["context"].get("weblog_variant"),
            )

            if not context or context.library not in libraries:
                break

            if context not in test_data:
                test_data[context] = []

            for test in scenario_data["tests"]:
                if test["outcome"] == "xpassed":
                    test_data[context].append(test["nodeid"])

    return test_data
