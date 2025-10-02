from http import HTTPStatus
import os
import re
import sys

import requests
from requests.auth import HTTPBasicAuth

from utils.tools import update_environ_with_local_env


update_environ_with_local_env()


def crawl_and_search(
    directories: tuple[str, ...], pattern: str, file_extensions: tuple[str, ...]
) -> list[tuple[str, str]]:
    regex = re.compile(pattern)

    result = []
    for directory in directories:
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename.endswith(file_extensions):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            for line in f:
                                match = regex.search(line)
                                if match:
                                    result.append((filepath, match.group(0)))
                    except (UnicodeDecodeError, OSError) as e:
                        print(f"Could not read file: {filepath} ({e})")

    return result


def add_label_on_jira_ticket(issue_key: str, label: str) -> None:
    if issue_key.startswith(("AIDM-", "FAKE-", "FNV-", "ISO-", "RFC-", "TIS-", "UTF-")):
        return

    jira_domain: str = "datadoghq.atlassian.net"
    url = f"https://{jira_domain}/rest/api/3/issue/{issue_key}"
    html_url = f"https://{jira_domain}/browse/{issue_key}"

    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    response = requests.get(
        url,
        headers=headers,
        auth=HTTPBasicAuth(os.environ["JIRA_API_EMAIL"], os.environ["JIRA_API_TOKEN"]),
        timeout=10,
    )

    if response.status_code != HTTPStatus.OK:
        print(f"❌ Failed to get {html_url}: {response.status_code} - {response.text}")
        sys.exit(1)

    if label in response.json()["fields"]["labels"]:
        print(f"✅  Label '{label}' already on issue {html_url}")
        return

    payload = {"update": {"labels": [{"add": label}]}}

    response = requests.put(
        url,
        json=payload,
        headers=headers,
        auth=HTTPBasicAuth(os.environ["JIRA_API_EMAIL"], os.environ["JIRA_API_TOKEN"]),
        timeout=10,
    )

    if response.status_code == HTTPStatus.NO_CONTENT:
        print(f"💾 Label '{label}' added to issue {html_url}")
    else:
        print(f"❌ Failed to add label on {html_url}: {response.status_code} - {response.text}")
        sys.exit(1)


def main() -> None:
    directories = ("manifests", "tests")
    pattern = r"\b([A-Z]+-\d+)\b"
    file_extensions = (".py", ".yml", ".yaml")

    tickets = set()
    for _, ticket in crawl_and_search(directories, pattern, file_extensions):
        tickets.add(ticket)

    for ticket in sorted(tickets):
        add_label_on_jira_ticket(issue_key=ticket, label="system-tests")


if __name__ == "__main__":
    main()
