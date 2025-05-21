import argparse
import logging
import os
import re
from typing import Any

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


def get_json(url: str, headers: dict | None = None, params: dict | None = None) -> Any:  # noqa: ANN401
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def main(
    language: str,
    log_pattern: str,
    repo_slug: str = "DataDog/system-tests-dashboard",
    workflow_file: str = "nightly.yml",
    branch: str = "main",
) -> None:
    environ = get_environ()
    gh_token = environ["GH_TOKEN"]
    headers = {"Authorization": f"token {gh_token}"}

    url = f"https://api.github.com/repos/{repo_slug}/actions/workflows/{workflow_file}/runs?"

    params: dict[str, str | int] = {"per_page": "100"}

    if branch:
        params["branch"] = branch

    data = get_json(url, headers=headers, params=params)
    workflows = data.get("workflow_runs", [])

    # sort to get the latest
    workflows = sorted(workflows, key=lambda w: w["created_at"], reverse=True)

    for workflow in workflows:
        workflow_id = workflow["id"]
        for attempt in range(1, workflow["run_attempt"] + 1):
            workflow_url = f"https://github.com/{repo_slug}/actions/runs/{workflow_id}/attempts/{attempt}"

            logging.info(f"Workflow #{workflow['run_number']}-{attempt} {workflow['created_at']} {workflow_url}")

            jobs_url = f"https://api.github.com/repos/{repo_slug}/actions/runs/{workflow_id}/attempts/{attempt}/jobs"
            params = {"per_page": "100"}
            page = 1

            jobs = get_json(jobs_url, headers=headers, params=params | {"page": page})

            while len(jobs["jobs"]) < jobs["total_count"]:
                page += 1
                jobs["jobs"] += get_json(jobs_url, headers=headers, params=params | {"page": page})["jobs"]

            for job in jobs["jobs"]:
                job_name = job["name"]
                if "artifact" in job_name or (language and language not in job_name):
                    continue

                if job["conclusion"] != "failure":
                    continue

                job_id = job["id"]
                response = requests.get(
                    f"https://api.github.com/repos/{repo_slug}/actions/jobs/{job_id}/logs", headers=headers, timeout=60
                )
                content = response.content.decode("utf-8")

                steps = re.split(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z ##\[group\]", content)

                for step in steps:
                    if log_pattern in step:
                        first_line = step.split("\n", 1)[0]
                        logging.info(
                            f"    ✅ Found in https://api.github.com/repos/{repo_slug}/actions/jobs/{job_id}/logs"
                        )
                        logging.info(f"        Name : {job_name}")
                        logging.info(f"        Step : {first_line}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="grep-nightly-logs", description="Grep into nightly logs to find a pattern")
    parser.add_argument(
        "--language",
        "-l",
        type=str,
        help="One of the supported Datadog languages",
        choices=[
            "cpp",
            "cpp_httpd",
            "cpp_nginx",
            "dotnet",
            "python",
            "ruby",
            "golang",
            "java",
            "nodejs",
            "php",
            "rust",
        ],
    )
    parser.add_argument(
        "--repo-slug",
        "-r",
        type=str,
        help="repository slug in the format owner/repo",
        default="DataDog/system-tests-dashboard",
    )
    parser.add_argument(
        "--workflow-file", "-w", type=str, help="Yml file name for the nightly workflow", default="nightly.yml"
    )
    parser.add_argument("pattern", type=str, help="Exact pattern to search for in the logs")
    args = parser.parse_args()

    main(language=args.language, log_pattern=args.pattern, repo_slug=args.repo_slug, workflow_file=args.workflow_file)
