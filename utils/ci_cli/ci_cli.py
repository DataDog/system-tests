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
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import gitlab
import yaml

GLAB_HOST = "gitlab.ddbuild.io"
GLAB_CONFIG = Path.home() / ".config" / "glab-cli" / "config.yml"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603


def check_gh() -> tuple[bool, str]:
    if not shutil.which("gh"):
        return False, "gh not found in PATH"

    result = _run(["gh", "auth", "status"])
    if result.returncode == 0:
        # Extract the logged-in account line
        for line in result.stdout.splitlines():
            if "Logged in to" in line or "✓" in line:
                return True, line.strip()
        return True, "authenticated"

    err = result.stderr.strip() or result.stdout.strip()
    return False, err or "not authenticated (run: gh auth login)"


def _is_host_resolvable(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ci_cli",
        description="Wrapper CLI for gh and glab CI tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # check
    check_p = sub.add_parser("check", help="Check that gh and glab are installed and authenticated")
    check_p.set_defaults(func=cmd_check)

    # gh
    gh_p = sub.add_parser("gh", help="GitHub CI commands (via gh)")
    gh_sub = gh_p.add_subparsers(dest="gh_command", required=True)

    gh_ci = gh_sub.add_parser("ci", help="List GitHub Actions runs")
    gh_ci.add_argument("--branch", "-b", help="Filter by branch")
    gh_ci.add_argument("--limit", "-n", type=int, default=10, help="Number of runs to show (default: 10)")
    gh_ci.set_defaults(func=cmd_gh_ci)

    # glab
    gl_p = sub.add_parser("glab", help="GitLab CI commands (via glab)")
    gl_sub = gl_p.add_subparsers(dest="glab_command", required=True)

    gl_ci = gl_sub.add_parser("ci", help="Show GitLab CI status")
    gl_ci.add_argument("--repo", "-r", help="GitLab repo (e.g. DataDog/auto_inject)")
    gl_ci.add_argument("--branch", "-b", help="Branch name")
    gl_ci.add_argument("--limit", "-n", type=int, default=10, help="Number of pipelines to show (default: 10)")
    gl_ci.set_defaults(func=cmd_glab_ci)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
