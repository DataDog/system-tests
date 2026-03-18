#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "python-gitlab>=4.0",
#   "pyyaml>=6.0",
# ]
# ///
"""CI CLI - wrapper for gh and glab CI tools."""

import argparse
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import gitlab
import yaml

GLAB_HOST = "gitlab.ddbuild.io"
GLAB_CONFIG = Path.home() / ".config" / "glab-cli" / "config.yml"

PR_REPO = "DataDog/system-tests"
PR_NUMBER = 6532


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603


def _is_host_resolvable(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False


# ---------------------------------------------------------------------------
# GitHub helpers (via gh CLI)
# ---------------------------------------------------------------------------


def _gh_api(path: str, params: dict[str, str | int] | None = None) -> object:
    url = path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    result = _run(["gh", "api", url])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def _gh_pr_branch() -> str:
    data = _gh_api(f"repos/{PR_REPO}/pulls/{PR_NUMBER}")
    assert isinstance(data, dict)
    return str(data["head"]["ref"])


def _gh_failed_jobs() -> list[dict[str, str]]:
    data = _gh_api(f"repos/{PR_REPO}/pulls/{PR_NUMBER}")
    assert isinstance(data, dict)
    sha = data["head"]["sha"]

    runs_data = _gh_api(f"repos/{PR_REPO}/actions/runs", {"head_sha": sha, "per_page": 100})
    assert isinstance(runs_data, dict)

    failed: list[dict[str, str]] = []
    for run in runs_data.get("workflow_runs", []):
        jobs_data = _gh_api(
            f"repos/{PR_REPO}/actions/runs/{run['id']}/jobs",
            {"filter": "latest", "per_page": 100},
        )
        assert isinstance(jobs_data, dict)
        for job in jobs_data.get("jobs", []):
            if job.get("conclusion") == "failure":
                failed.append(
                    {
                        "id": str(job["id"]),
                        "name": job["name"],
                        "workflow": run["name"],
                        "url": job["html_url"],
                    }
                )
    return failed


# ---------------------------------------------------------------------------
# GitLab helpers (via python-gitlab)
# ---------------------------------------------------------------------------


def _glab_token() -> str | None:
    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("PRIVATE_TOKEN")
    if token:
        return token
    if GLAB_CONFIG.exists():
        cfg = yaml.safe_load(GLAB_CONFIG.read_text())
        return cfg.get("hosts", {}).get(GLAB_HOST, {}).get("token") or None
    return None


def _gitlab_client() -> gitlab.Gitlab:
    token = _glab_token()
    if not token:
        msg = f"no token found for {GLAB_HOST} — run: glab auth login --hostname {GLAB_HOST}"
        raise RuntimeError(msg)
    return gitlab.Gitlab(f"https://{GLAB_HOST}", private_token=token)


def _gl_failed_jobs(branch: str) -> list[dict[str, str]]:
    gl = _gitlab_client()
    project = gl.projects.get(PR_REPO)
    pipelines = project.pipelines.list(ref=branch, per_page=1, get_all=False)
    if not pipelines:
        return []
    pipeline = pipelines[0]
    all_jobs = pipeline.jobs.list(get_all=True)
    return [
        {
            "id": str(job.id),
            "name": job.name,
            "stage": job.stage,
            "url": job.web_url,
        }
        for job in all_jobs
        if job.status == "failed"
    ]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def check_gh() -> tuple[bool, str]:
    if not shutil.which("gh"):
        return False, "gh not found in PATH"

    result = _run(["gh", "auth", "status"])
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "Logged in to" in line or "✓" in line:
                return True, line.strip()
        return True, "authenticated"

    err = result.stderr.strip() or result.stdout.strip()
    return False, err or "not authenticated (run: gh auth login)"


def check_glab() -> tuple[bool, str]:
    if not _is_host_resolvable(GLAB_HOST):
        return False, f"{GLAB_HOST} not resolvable — are you on VPN?"

    try:
        gl = _gitlab_client()
    except RuntimeError as e:
        return False, str(e)

    try:
        gl.auth()
        return True, f"authenticated as {gl.user.username} on {GLAB_HOST}"  # type: ignore[union-attr]
    except gitlab.exceptions.GitlabAuthenticationError:
        return False, f"token rejected by {GLAB_HOST}"
    except gitlab.exceptions.GitlabError as e:
        return False, f"gitlab error: {e}"


def cmd_check(args: argparse.Namespace) -> int:  # noqa: ARG001
    checks = [
        ("gh (GitHub CLI)", check_gh),
        ("glab (GitLab CLI)", check_glab),
    ]

    all_ok = True
    for name, checker in checks:
        ok, msg = checker()
        status = "✓" if ok else "✗"
        print(f"  {status} {name}: {msg}")
        if not ok:
            all_ok = False

    return 0 if all_ok else 1


def cmd_pr(args: argparse.Namespace) -> int:  # noqa: ARG001
    print(f"PR #{PR_NUMBER} — {PR_REPO}\n")

    # --- GitHub Actions ---
    print("GitHub Actions — failed jobs:")
    branch: str | None = None
    try:
        branch = _gh_pr_branch()
        gh_jobs = _gh_failed_jobs()
        if gh_jobs:
            for job in gh_jobs:
                print(f"  ✗ [{job['workflow']}] {job['name']}")
                print(f"    {job['url']}")
        else:
            print("  ✓ no failed jobs")
    except Exception as e:  # noqa: BLE001
        print(f"  error: {e}", file=sys.stderr)

    print()

    # --- GitLab CI ---
    print(f"GitLab CI ({GLAB_HOST}) — failed jobs:")
    if not _is_host_resolvable(GLAB_HOST):
        print(f"  skipped: {GLAB_HOST} not resolvable — are you on VPN?")
        return 1

    if branch is None:
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()

    try:
        gl_jobs = _gl_failed_jobs(branch)
        if gl_jobs:
            for job in gl_jobs:
                print(f"  ✗ [{job['stage']}] {job['name']}  (job id: {job['id']})")
                print(f"    {job['url']}")
        else:
            print("  ✓ no failed jobs")
    except Exception as e:  # noqa: BLE001
        print(f"  error: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_gh_ci(args: argparse.Namespace) -> int:
    cmd = ["gh", "run", "list"]
    if args.branch:
        cmd += ["--branch", args.branch]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    result = _run(cmd)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def cmd_glab_ci(args: argparse.Namespace) -> int:
    if not _is_host_resolvable(GLAB_HOST):
        print(f"error: {GLAB_HOST} not resolvable — are you on VPN?", file=sys.stderr)
        return 1

    try:
        gl = _gitlab_client()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not args.repo:
        print("error: --repo is required (e.g. DataDog/system-tests)", file=sys.stderr)
        return 1

    try:
        project = gl.projects.get(args.repo)
        kwargs: dict[str, object] = {"per_page": args.limit, "get_all": False}
        if args.branch:
            kwargs["ref"] = args.branch
        pipelines = project.pipelines.list(**kwargs)
    except gitlab.exceptions.GitlabError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not pipelines:
        print("no pipelines found")
        return 0

    col = "{:<10} {:<12} {:<30} {:<40}"
    print(col.format("ID", "STATUS", "REF", "URL"))
    print("-" * 95)
    for p in pipelines:
        print(col.format(p.id, p.status, p.ref[:30], p.web_url))
    return 0


def cmd_claude(args: argparse.Namespace) -> int:  # noqa: ARG001
    script = Path(__file__).resolve()
    print(f"""\
# CI debug instructions for PR #{PR_NUMBER} ({PR_REPO})

You are helping debug CI failures on PR #{PR_NUMBER} in the {PR_REPO} repository.
The CI runs on two platforms: GitHub Actions and GitLab CI (`{GLAB_HOST}`).

## Tools available

All commands are run via:
```
uv run {script} <command>
```

### List all failed jobs (both platforms)
```
uv run {script} pr
```
Output includes:
- GitHub Actions: workflow name, job name, URL
- GitLab CI: stage, job name, job ID, URL

The GitLab **job ID** shown is needed to fetch artifacts.

### Download and inspect GitLab job artifacts
```
uv run {script} glab artifacts <job-id>
```
Prints a local path to a temp directory containing the unpacked artifact files.
Artifacts typically include logs, test reports, junit XML, and other outputs.

## Recommended debugging workflow

1. Run `pr` to get the list of failed jobs.
2. For each failed GitLab job, run `glab artifacts <job-id>` to get the artifact path.
3. Explore the unpacked directory — look for:
   - `*.log` or `*.txt` files for raw job output
   - `junit*.xml` / `report*.xml` for structured test results
   - Any `*error*` or `*fail*` named files
4. Read the relevant files and identify the root cause.
5. For GitHub Actions failures, follow the URL from step 1 to read the logs directly.

## Auth requirements

- GitHub: `gh` CLI must be authenticated (`gh auth login`)
- GitLab: VPN required; token read from `~/.config/glab-cli/config.yml`
- Run `uv run {script} check` to verify both are ready before starting.
""")
    return 0


def cmd_glab_artifacts(args: argparse.Namespace) -> int:
    if not _is_host_resolvable(GLAB_HOST):
        print(f"error: {GLAB_HOST} not resolvable — are you on VPN?", file=sys.stderr)
        return 1

    try:
        gl = _gitlab_client()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        project = gl.projects.get(PR_REPO)
        job = project.jobs.get(args.job_id)
        print(f"Downloading artifacts for job {args.job_id} ({job.name})...", file=sys.stderr)
        artifact_bytes = job.artifacts()
    except gitlab.exceptions.GitlabError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not artifact_bytes:
        print("error: no artifacts found for this job", file=sys.stderr)
        return 1

    tmpdir = tempfile.mkdtemp(prefix=f"ci_artifacts_{args.job_id}_")
    with zipfile.ZipFile(io.BytesIO(artifact_bytes)) as zf:
        zf.extractall(tmpdir)

    print(tmpdir)
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ci_cli",
        description="Wrapper CLI for gh and glab CI tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # check
    check_p = sub.add_parser("check", help="Check that gh and glab are installed and authenticated")
    check_p.set_defaults(func=cmd_check)

    # claude
    claude_p = sub.add_parser("claude", help="Print CLAUDE.md-style instructions for debugging this PR's CI")
    claude_p.set_defaults(func=cmd_claude)

    # pr
    pr_p = sub.add_parser("pr", help=f"List all failed CI jobs for PR #{PR_NUMBER} (GitHub + GitLab)")
    pr_p.set_defaults(func=cmd_pr)

    # gh
    gh_p = sub.add_parser("gh", help="GitHub CI commands (via gh)")
    gh_sub = gh_p.add_subparsers(dest="gh_command", required=True)

    gh_ci = gh_sub.add_parser("ci", help="List GitHub Actions runs")
    gh_ci.add_argument("--branch", "-b", help="Filter by branch")
    gh_ci.add_argument("--limit", "-n", type=int, default=10, help="Number of runs to show (default: 10)")
    gh_ci.set_defaults(func=cmd_gh_ci)

    # glab
    gl_p = sub.add_parser("glab", help="GitLab CI commands (via python-gitlab)")
    gl_sub = gl_p.add_subparsers(dest="glab_command", required=True)

    gl_ci = gl_sub.add_parser("ci", help="List GitLab pipelines")
    gl_ci.add_argument("--repo", "-r", help="GitLab repo (e.g. DataDog/auto_inject)")
    gl_ci.add_argument("--branch", "-b", help="Branch name")
    gl_ci.add_argument("--limit", "-n", type=int, default=10, help="Number of pipelines to show (default: 10)")
    gl_ci.set_defaults(func=cmd_glab_ci)

    gl_art = gl_sub.add_parser("artifacts", help="Download and unpack job artifacts to a temp directory")
    gl_art.add_argument("job_id", type=int, help="GitLab job ID")
    gl_art.set_defaults(func=cmd_glab_artifacts)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
