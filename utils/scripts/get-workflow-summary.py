from collections import defaultdict
import os
import sys

import requests


def get_environ():
    environ = {**os.environ}

    try:
        with open(".env", encoding="utf-8") as f:
            lines = [l.replace("export ", "").strip().split("=") for l in f if l.strip()]
            environ = {**environ, **dict(lines)}
    except FileNotFoundError:
        pass

    return environ


def get_jobs(session, repo_slug: str, run_id: int) -> list:
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

    return jobs


def main(repo_slug: str, run_id: int) -> None:

    environ = get_environ()

    with requests.Session() as session:
        if "GH_TOKEN" in environ:
            session.headers["Authorization"] = environ["GH_TOKEN"]

        jobs = get_jobs(session, repo_slug, run_id)

        failing_steps = defaultdict(list)

        for job in jobs:
            if job["conclusion"] != "failure":
                continue

            for step in job["steps"]:
                if step["conclusion"] == "failure":
                    failing_steps[step["name"]].append((job, step))

        for step_name, items in failing_steps.items():
            print(f"❌ **Failures for `{step_name}`**\n")
            for job, step in sorted(items, key=lambda x: x[0]["name"]):
                url = job["html_url"]
                print(f"* [{job['name']}]({url}#step:{step['number']})")

            print()


if __name__ == "__main__":
    main("DataDog/system-tests", sys.argv[1])
