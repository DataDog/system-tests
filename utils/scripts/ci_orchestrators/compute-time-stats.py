from collections import defaultdict
from datetime import UTC, date as date_type, datetime
import logging
import os
from pathlib import Path
import re
from typing import Any

import requests
from datetime import timedelta
import json

WEEKEND_DAYS = (5, 6)  # Saturday, Sunday


HTTP_OK = 200
GITHUB_API_PAGE_SIZE = 100
CSV_COLUMNS_WITHOUT_ATTEMPT = 7


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    auth: Any = None,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    logging.debug(f"GET {url} {params}")

    headers = headers or {}
    headers["Content-Type"] = "application/json"

    r = requests.get(url, params=params, headers=headers, auth=auth, timeout=10)

    if r.status_code != HTTP_OK:
        raise ValueError(f"Fail to load archive {url}. Status code: {r.status_code}, response: '{r.text}'")

    return r.json()


def get_jobs(jobs_url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    page = 1

    result: list[dict[str, Any]] = []

    while True:
        jobs = get_json(jobs_url, headers=headers, params={"per_page": GITHUB_API_PAGE_SIZE, "page": page})

        if len(jobs["jobs"]) == 0:
            return result

        result += jobs["jobs"]

        page += 1


def get_environ() -> dict[str, str]:
    environ = {**os.environ}

    try:
        with open(".env", "r", encoding="utf-8") as f:
            lines = [line.replace("export ", "").strip().split("=") for line in f if line.strip()]
            environ = {**environ, **dict(lines)}
    except FileNotFoundError:
        # if .env file is missing, do not update environ
        pass

    return environ


class Data:
    def __init__(self, date: date_type | None = None) -> None:
        self.date = date or datetime.now(UTC).date()
        self._failures_counts: defaultdict[str, int] = defaultdict(int)
        self._run_failures_counts_by_language: defaultdict[str, int] = defaultdict(int)
        self._scenario_durations: defaultdict[str, defaultdict[str, dict[str | None, float]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._build_durations: defaultdict[str, dict[tuple[str, str, str | None], int]] = defaultdict(dict)
        self.run_count = 0
        self._run_count_by_language: defaultdict[str, int] = defaultdict(int)

        self._build_failures_counts_by_language: defaultdict[str, int] = defaultdict(int)
        self._build_counts_by_language: defaultdict[str, int] = defaultdict(int)

        self.step_categories = {
            r"(Set up|Complete) job": "ci-setup",
            r"(Checkout|Post Checkout)": "ci-setup",
            r"Log in to the Container registry": "ci-setup",
            r"(Post )?Set up (QEMU|Docker Buildx)": "ci-setup",
            r"Set up QEMU for docker cross platform setup": "ci-setup",
            r"(Post )?Login to GitHub Container Registry": "ci-setup",
            r"Prepare arm runner": "ci-setup",
            r"(Compress|Upload) (artifact|logs)": "ci-setup",
            r"(Post )?Setup python 3\.9": "ci-setup",
            r"Load (library binary|agent binary|PHP appsec|WAF rule set)": "load-component",
            r"Load (PHP|Ruby|C\+\+) library binary .*": "load-component",
            r"Get binaries artifact": "load-component",
            r"(Post )?Pull images": "build",
            r"(Build|build).*": "build",
            r"(Post )?Install runner": "build",
            r"Run [\w ]+ scenario": "run",
            r"Run \./run\.sh [A-Z_0-9]+.*": "run",
            r"Run parametric (tests )?\(with timeout\)": "run",
            r"Run parametric (tests )?\(without timeout\)": "run",
            r"Upload results CI Visibility": "post-run",
            r"Push results to Feature Parity Dashboard": "post-run",
            r"Print fancy log report": "post-run",
            r"Run all scenarios in replay mode": "post-run",
        }

    def _find_category(self, name: str) -> str:
        for pattern, category in self.step_categories.items():
            if re.fullmatch(pattern, name):
                return category

        raise ValueError(f"Category not found for '{name}'")

    @property
    def filename(self) -> str:
        return f"stats/{self.date}.csv"

    def load(self, *, force_reload: bool = False) -> None:
        if not Path(self.filename).is_file() or force_reload:
            self.get_from_github_actions(
                "DataDog/system-tests-dashboard",
                ("nightly.yml",),
                "main",
            )

        with open(self.filename, encoding="utf-8") as f:
            f.readline()

            for line in f:
                self._append(line)

    def get_run_statistics(self) -> dict[str, Any]:
        result: dict[str, Any] = self._scenario_durations

        for scenario, lang_durations in result.items():
            scenario_average = 0
            for library, weblog_durations in lang_durations.items():
                average = sum(weblog_durations.values()) / len(weblog_durations)
                result[scenario][library]["*"] = average
                scenario_average += average / len(lang_durations)

            result[scenario]["*"] = scenario_average

        return self._scenario_durations

    def get_build_statistics(self) -> dict[str, Any]:
        global_average = 0
        result: dict[str, Any] = {
            library: {build_key[2]: value for build_key, value in weblog_durations.items()}
            for library, weblog_durations in self._build_durations.items()
        }

        for library, weblog_durations in result.items():
            average = sum(weblog_durations.values()) / len(weblog_durations)
            result[library]["*"] = average
            global_average += average / len(result)

        result["*"] = global_average
        return result

    def get_from_github_actions(self, repo_slug: str, workflow_files: tuple[str, ...], branch: str) -> None:
        logging.info(f"Get runs from {self.date}")

        environ = get_environ()
        gh_token = environ["GH_TOKEN"]
        headers = {"Authorization": f"token {gh_token}"}

        lines = []

        def export(*args: Any) -> None:  # noqa: ANN401
            lines.append(";".join(map(str, args)) + "\n")

        export(
            "workflow",
            "job",
            "job_name",
            "step_name",
            "status",
            "conclusion",
            "duration",
            "attempt",
            "is_last_attempt",
        )

        for workflow_file in workflow_files:
            url = f"https://api.github.com/repos/{repo_slug}/actions/workflows/{workflow_file}/runs"
            params = {
                "per_page": 100,
                "branch": branch,
                "created": f"{self.date}..{self.date}",
            }

            workflows = get_json(url, headers=headers, params=params)
            assert workflows["total_count"] < GITHUB_API_PAGE_SIZE

            for workflow in workflows["workflow_runs"]:
                for attempt in range(1, workflow["run_attempt"] + 1):
                    workflow_id = workflow["id"]
                    jobs_url = (
                        f"https://api.github.com/repos/{repo_slug}/actions/runs/{workflow_id}/attempts/{attempt}/jobs"
                    )

                    jobs = get_jobs(jobs_url, headers=headers)
                    for job in jobs:
                        for step in job["steps"]:
                            if step["started_at"] is not None and step["completed_at"] is not None:
                                started_at = datetime.fromisoformat(step["started_at"])
                                completed_at = datetime.fromisoformat(step["completed_at"])
                                duration = (completed_at - started_at).total_seconds()
                                if step["conclusion"] != "skipped":
                                    export(
                                        workflow["id"],
                                        job["id"],
                                        job["name"],
                                        step["name"],
                                        step["status"],
                                        step["conclusion"],
                                        duration,
                                        attempt,
                                        attempt == workflow["run_attempt"],
                                    )

        with open(self.filename, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def _append(self, csv_line: str) -> None:
        items = csv_line[:-1].split(";")

        if len(items) == CSV_COLUMNS_WITHOUT_ATTEMPT:
            items.append("1")
            items.append("True")

        (
            workflow,
            job,
            job_name,
            step_name,
            _,  # status
            conclusion,
            duration,
            __,  # attempt
            is_last_attempt,
        ) = items

        job_name = job_name.lower()

        if job_name in ("post_system-tests",):  # skip some jobs
            return

        for excluded_job in (
            "lib-injection",
            "compute-matrix",
            "get scenarios",
            "get weblogs",
            "get_dev_artifacts",
            "get parameters",
        ):
            if excluded_job in job_name:
                return

        for seps in ",()/":
            job_name = job_name.replace(seps, " ")

        keys = {k for k in job_name.split(" ") if k.strip()}

        ci = None
        lang = None
        weblog = None

        for key in keys:
            if key in ("nightly", "end-to-end"):
                continue

            if key.isdecimal():
                continue

            if key in ("dev", "prod"):
                assert ci is None, f"CI already set for '{job_name}'"
                ci = key
            elif key in ("php", "python", "ruby", "nodejs", "golang", "cpp", "java", "dotnet", "python_http"):
                assert lang is None, f"lang already set for '{job_name}'"
                lang = key
            else:
                assert weblog is None, f"weblog already set for '{job_name}' : {weblog} vs {key}"
                weblog = key

        if lang == "python_http":
            lang = "python"

        assert ci is not None, f"CI not found for '{job_name}'"
        assert lang is not None, f"Lang not found for '{job_name}'"

        category = self._find_category(step_name)
        duration_seconds = float(duration)

        if category == "run" and is_last_attempt == "True":
            name = step_name.replace("./run.sh ", "")
            name = name.replace(" scenario", "")
            name = name.replace(" $REPORT_PARAMS", "")
            name = name.replace(" (without timeout)", "")
            name = name.replace(" tests (with timeout)", "")
            name = name.upper()
            name = name.replace("RUN ", "")

            self.run_count += 1
            self._run_count_by_language[lang] += 1
            if conclusion != "success":
                scenario_category = name

                if scenario_category.startswith("APPSEC"):
                    scenario_category = "APPSEC*"
                elif scenario_category.startswith("REMOTE_CONFIG"):
                    scenario_category = "REMOTE_CONFIG*"
                elif scenario_category.startswith("TELEMETRY"):
                    scenario_category = "TELEMETRY*"
                elif scenario_category.startswith("DEBUGGER"):
                    scenario_category = "DEBUGGER*"
                elif (
                    scenario_category.startswith(("LIBRARY_CONF", "TRACING_CONFIG", "TRACE_PROPAGATION_STYLE_W3C"))
                    or scenario_category == "SAMPLING"
                ):
                    scenario_category = "LIBRARY_CONF*"
                elif scenario_category in ("CROSSED_TRACING_LIBRARIES", "INTEGRATIONS"):
                    scenario_category = "INTEGRATIONS*"

                self._failures_counts[scenario_category] += 1
                self._run_failures_counts_by_language[lang] += 1

            self._scenario_durations[name][lang][weblog] = duration_seconds

        elif category == "build":
            self._build_counts_by_language[lang] += 1
            if conclusion != "success":
                self._build_failures_counts_by_language[lang] += 1

            if ci == "dev":  # use only dev for durations
                build_key = (workflow, job, weblog)
                if build_key not in self._build_durations[lang]:
                    self._build_durations[lang][build_key] = 0

                self._build_durations[lang][build_key] += int(duration_seconds)

    @property
    def failures_rate(self) -> dict[str, float]:
        return {k: v / self.run_count for k, v in self._failures_counts.items()}

    @property
    def run_failures_rate_by_language(self) -> dict[str, float]:
        return {
            lang: v / self._run_count_by_language[lang] for lang, v in self._run_failures_counts_by_language.items()
        }

    @property
    def build_failures_rate_by_language(self) -> dict[str, float]:
        return {
            lang: v / self._build_counts_by_language[lang]
            for lang, v in self._build_failures_counts_by_language.items()
        }

    def get_scenario_durations(self, name: str) -> dict[str, float]:
        return {k: sum(v.values()) / len(v) for k, v in self._scenario_durations[name].items()}

    @property
    def build_durations(self) -> dict[str, float]:
        return {k: sum(v.values()) / len(v) for k, v in self._build_durations.items()}

    def __str__(self) -> str:
        return f"{self.run_count} {self._failures_counts}"


def _sort(data: Any) -> Any:  # noqa: ANN401
    if isinstance(data, dict):
        return {k: _sort(data[k]) for k in sorted(data)}

    return data


def main() -> None:
    date = datetime.now(UTC).date() - timedelta(days=1)

    while date.weekday() in WEEKEND_DAYS:
        date -= timedelta(days=1)

    data = Data(date)
    data.load()

    result = _sort(
        {
            "build": data.get_build_statistics(),
            "run": data.get_run_statistics(),
        }
    )

    print(json.dumps(result))


if __name__ == "__main__":
    main()
