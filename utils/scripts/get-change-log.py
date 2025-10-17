#!/usr/bin/env python3
import os
import sys
import argparse
from datetime import datetime, timedelta, UTC
from typing import Any
import requests

API_URL = "https://api.github.com/graphql"

QUERY = """
query ($query: String!, $after: String) {
  search(type: ISSUE, query: $query, first: 100, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        title
        url
        author { login }
        mergedAt
        labels(first: 100) {
          nodes { name }
        }
      }
    }
  }
}
"""


def last_completed_month_range(month: int | None = None) -> tuple[str, str, int, int]:
    today = datetime.now(UTC).date()

    if month is not None:
        # Validate month
        if not 1 <= month <= 12:  # noqa: PLR2004
            raise ValueError("Month must be between 1 and 12")

        # Use the specified month for the current year
        target_date = today.replace(month=month, day=1)

        # If the specified month is in the future, use the previous year
        if target_date > today:
            target_date = target_date.replace(year=today.year - 1)

        # Get the last day of the specified month
        if month == 12:  # noqa: PLR2004
            next_month = target_date.replace(year=target_date.year + 1, month=1)
        else:
            next_month = target_date.replace(month=month + 1)

        last_day = next_month - timedelta(days=1)
        return target_date.isoformat(), last_day.isoformat(), target_date.year, target_date.month
    # Original logic for last completed month
    first_of_current = today.replace(day=1)
    last_of_prev = first_of_current - timedelta(days=1)
    first_of_prev = last_of_prev.replace(day=1)
    return first_of_prev.isoformat(), last_of_prev.isoformat(), first_of_prev.year, first_of_prev.month


def gh_request(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    r = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"query": query, "variables": variables},
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise RuntimeError(j["errors"])
    return j["data"]


def print_pr_data(month: int | None = None) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Please set GITHUB_TOKEN in your environment.")
        sys.exit(1)

    start_date, end_date, year, month = last_completed_month_range(month)
    q = f"repo:DataDog/system-tests is:pr merged:{start_date}..{end_date}"
    target_label = "build-python-base-images"

    pr_prints = []
    n_prs = 0

    after = None
    while True:
        data = gh_request(token, QUERY, {"query": q, "after": after})

        for pr in data["search"]["nodes"]:
            n_prs += 1
            labels = [labels["name"] for labels in pr["labels"]["nodes"]]
            # if True:
            if target_label in labels:
                merged_at = pr["mergedAt"][:10]
                title = pr["title"]
                url = pr["url"]
                author = pr["author"]["login"]

                pr_prints.append(f"* {merged_at} [{title}]({url}) by @{author}")

        if not data["search"]["pageInfo"]["hasNextPage"]:
            break
        after = data["search"]["pageInfo"]["endCursor"]

    print(f"### {year}-{month:02d} ({n_prs} PR merged)\n")
    for line in pr_prints:
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate changelog for system-tests repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python get-change-log.py                    # Use last completed month
  python get-change-log.py --month 12         # Use December of current year
  python get-change-log.py --month 1          # Use January of current year
        """,
    )

    parser.add_argument(
        "--month",
        type=int,
        choices=range(1, 13),
        help="Month to generate changelog for (1-12). If not specified, uses the last completed month.",
    )

    args = parser.parse_args()
    print_pr_data(args.month)


if __name__ == "__main__":
    main()
