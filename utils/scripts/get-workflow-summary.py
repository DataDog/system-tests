import argparse
from collections import defaultdict
import logging
import os
import sys

import requests


def get_environ() -> dict[str, str]:
    environ = {**os.environ}

    try:
        with open(".env", encoding="utf-8") as f:
            lines = [line.replace("export ", "").strip().split("=") for line in f if line.strip()]
            environ = {**environ, **dict(lines)}
    except FileNotFoundError:
        pass

    return environ


def get_jobs(session: requests.Session, repo_slug: str, run_id: int) -> list:
    jobs = []
    params = {"per_page": 100, "page": 1}
    while True:
        response = session.get(f"https://api.github.com/repos/{repo_slug}/actions/runs/{run_id}/jobs", params=params)
        response.raise_for_status()
        items = response.json()["jobs"]
        if len(items) == 0:
            break

        jobs += items
        params["page"] += 1

    logging.info(f"Found {len(jobs)} jobs")

    return jobs


def main(repo_slug: str, run_id: int, output: str) -> None:
    logging.info(f"Getting workflow summary for https://github.com/{repo_slug}/actions/runs/{run_id}")
    environ = get_environ()

    result: list[str] = []

    with requests.Session() as session:
        if "GITHUB_TOKEN" in environ:
            session.headers["Authorization"] = environ["GITHUB_TOKEN"]

        jobs = get_jobs(session, repo_slug, run_id)

        failing_steps = defaultdict(list)

        for job in jobs:
            if job["name"] in ("all-jobs-are-green", "fancy-report", "All jobs are green", "all-jobs-are-green-legacy"):
                logging.info(f"Skipping job {job['name']}")
                continue

            if job["conclusion"] != "failure":
                continue

            for step in job["steps"]:
                if step["conclusion"] == "failure":
                    failing_steps[step["name"]].append((job, step))

        for step_name, items in failing_steps.items():
            result.append(f"❌ **Failures for `{step_name}`**\n")
            for job, step in sorted(items, key=lambda x: x[0]["name"]):
                url = job["html_url"]
                result.append(f"* [{job['name']}]({url}#step:{step['number']})")

            result.append("")

        if output:
            logging.info(f"Writing output to {output}")
            with open(output, "w") as f:
                f.write("\n".join(result))
        else:
            logging.info("Writing output to stdout")
            print("\n".join(result))
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="get-workflow-summary", description="List all failing step of a github workflow, and pretty print them"
    )

    parser.add_argument("repo_slug", type=str, help="Repo slug of the workflow")

    parser.add_argument("run_id", type=int, help="Run Id of the workflow")

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="",
        help="Output file. If not provided, output to stdout",
    )
    args = parser.parse_args()

    # put back info once issue on job conclusion=None is fixed
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s", stream=sys.stderr)

    main(
        repo_slug=args.repo_slug,
        run_id=args.run_id,
        output=args.output,
    )
