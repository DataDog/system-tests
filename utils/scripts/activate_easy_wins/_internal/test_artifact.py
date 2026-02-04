from dataclasses import dataclass, field
import enum
from pathlib import Path
import re
import requests
import zipfile
from pygtrie import StringTrie
import shutil

from .types import Context
import json


def pull_artifact(url: str, token: str, data_dir: Path) -> None:
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

        print("Downloading artifact...")
        downloaded = 0
        last_percent_reported = -10

        with open("data.zip", "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded * 100) // total_size
                        if percent >= last_percent_reported + 10:
                            last_percent_reported = (percent // 10) * 10
                            print(f"  {last_percent_reported}% downloaded ({downloaded // 1024 // 1024} MB)")

        print("Download complete.")

    # Extract the downloaded zip file
    shutil.rmtree(data_dir)
    with zipfile.ZipFile("data.zip") as z:
        z.extractall(data_dir)


class ActivationStatus(enum.Enum):
    XPASS = "xpass"
    XFAIL = "xfail"
    PASS = "pass"  # noqa: S105
    NONE = "none"


@dataclass
class TestData:
    xpass_nodes: set[str] = field(default_factory=set)
    xfail_nodes: set[str] = field(default_factory=set)
    trie: StringTrie = field(default_factory=StringTrie)
    nodeid_to_owners: dict[str, set[str]] = field(default_factory=dict)

    def __iter__(self):
        yield self.xpass_nodes
        yield self.trie


def parse_artifact_data(
    data_dir: Path, libraries: list[str], excluded_owners: set[str] | None = None
) -> tuple[dict[Context, TestData], dict[str, set[str]]]:
    test_data: dict[Context, TestData] = {}
    weblogs: dict[str, set[str]] = {}

    for directory in data_dir.iterdir():
        if "_dev_" in directory.name in directory.name:
            continue

        for scenario_dir in directory.iterdir():
            try:
                with scenario_dir.joinpath("report.json").open(encoding="utf-8") as file:
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
                test_data[context] = TestData()

            library_name = scenario_data["context"]["library_name"]
            if library_name not in weblogs:
                weblogs[library_name] = set()
            weblogs[library_name].add(scenario_data["context"]["weblog_variant"])

            excluded_owners_set = excluded_owners or set()
            for test in scenario_data["tests"]:
                # Get code owners from test metadata
                test_owners = set()
                if "metadata" in test and "owners" in test["metadata"]:
                    test_owners = set(test["metadata"]["owners"])

                # Store nodeid to owners mapping
                test_data[context].nodeid_to_owners[test["nodeid"]] = test_owners

                # If test is xpassed and has excluded owners, treat it as xfailed instead
                outcome = test["outcome"]
                if outcome == "xpassed" and excluded_owners_set and test_owners & excluded_owners_set:
                    outcome = "xfailed"

                nodeid = test["nodeid"].split("[")[0]

                if nodeid not in test_data[context].xfail_nodes:
                    if outcome == "xpassed":
                        test_data[context].xpass_nodes.add(nodeid)
                    else:
                        test_data[context].xfail_nodes.add(nodeid)
                        if nodeid in test_data[context].xpass_nodes:
                            test_data[context].xpass_nodes.remove(nodeid)

                nodeid = nodeid.replace("::", "/") + "/"
                parts = re.finditer("/", nodeid)
                for part in parts:
                    nodeid_slice = nodeid[: part.end()].rstrip("/")
                    previous = test_data[context].trie.get(nodeid_slice)

                    if outcome == "xpassed":
                        if part.end() == len(nodeid) and previous:
                            pass
                        elif previous in (ActivationStatus.XFAIL, ActivationStatus.NONE):
                            test_data[context].trie[nodeid_slice] = ActivationStatus.NONE
                        else:
                            test_data[context].trie[nodeid_slice] = ActivationStatus.XPASS

                    if outcome == "xfailed":
                        if part.end() == len(nodeid):
                            test_data[context].trie[nodeid_slice] = ActivationStatus.XFAIL
                        elif previous in (ActivationStatus.XPASS, ActivationStatus.PASS, ActivationStatus.NONE):
                            test_data[context].trie[nodeid_slice] = ActivationStatus.NONE
                        else:
                            test_data[context].trie[nodeid_slice] = ActivationStatus.XFAIL

                    if outcome == "passed":
                        if previous in (ActivationStatus.XFAIL, ActivationStatus.NONE):
                            test_data[context].trie[nodeid_slice] = ActivationStatus.NONE
                        else:
                            test_data[context].trie[nodeid_slice] = ActivationStatus.PASS

    return test_data, weblogs
