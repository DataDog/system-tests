import argparse
import json
import os
import re
import sys
from typing import TextIO

# do not include otel in system-tests CI by default, as the staging backend is not stable enough
default_libraries = [
    "cpp",
    "cpp_httpd",
    "cpp_nginx",
    "dotnet",
    "golang",
    "java",
    "nodejs",
    "php",
    "python",
    "ruby",
    "python_lambda",
]

libraries = (
    "cpp|cpp_httpd|cpp_nginx|dotnet|golang|java|nodejs|php|python|ruby|java_otel|python_otel|nodejs_otel|python_lambda"
)


def get_impacted_libraries(modified_file: str) -> list[str]:
    """Return the list of impacted libraries by this file"""
    if modified_file.endswith((".md", ".rdoc", ".txt")):
        # modification in documentation file
        return []

    patterns = [
        rf"^manifests/({libraries})\.",
        rf"^utils/build/docker/({libraries})/",
        rf"^lib-injection/build/docker/({libraries})/",
    ]

    for pattern in patterns:
        if match := re.search(pattern, modified_file):
            return [match[1]]

    return default_libraries


def main() -> None:
    parser = argparse.ArgumentParser(description="AWS SSI Registration Tool")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="",
        help="Output file. If not provided, output to stdout",
    )

    args = parser.parse_args()

    result = set()

    if os.environ.get("GITHUB_EVENT_NAME", "pull_request") != "pull_request":
        print("Not in PR => run all libraries")
        result |= set(default_libraries)

    else:
        pr_title = os.environ.get("GITHUB_PR_TITLE", "").lower()
        match = re.search(rf"^\[({libraries})(?:@([^\]]+))?\]", pr_title)
        user_choice = None
        branch_selector = None
        prevent_library_selector_mismatch = True
        if match:
            print(f"PR title matchs => run {match[1]}")
            user_choice = match[1]
            result.add(user_choice)

            # if users specified a branch, another job will prevent the merge
            # so let user do what he/she wants :
            branch_selector = match[2]
            prevent_library_selector_mismatch = branch_selector is None

        print("Inspect modified files to determine impacted libraries...")

        with open("modified_files.txt", "r", encoding="utf-8") as f:
            modified_files: list[str] = [line.strip() for line in f]

        for file in modified_files:
            impacted_libraries = get_impacted_libraries(file)

            if file.endswith((".md", ".rdoc", ".txt")):
                # modification in documentation file
                continue

            if user_choice is None:
                # user let the script pick impacted libraries
                result |= set(impacted_libraries)
            elif prevent_library_selector_mismatch and len(impacted_libraries) > 0:
                # user specified a library in the PR title
                # and there are some impacted libraries
                if file.startswith("tests/"):
                    # modification in tests files are complex, trust user
                    ...
                elif impacted_libraries != [user_choice]:
                    # only acceptable use case : impacted library exactly matches user choice
                    print(
                        f"""File {file} is modified, and it may impact {', '.join(impacted_libraries)}.
                        Please remove the PR title prefix [{user_choice}]"""
                    )
                    sys.exit(1)

    populated_result = [
        {
            "library": library,
            "version": "prod",
        }
        for library in sorted(result)
    ] + [
        {
            "library": library,
            "version": "dev",
        }
        for library in sorted(result)
        if "otel" not in library and library not in ("cpp_nginx",)
    ]

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            print_result(populated_result, result, f)
    else:
        print_result(populated_result, result, sys.stdout)


def print_result(populated_result: list, result: set[str], f: TextIO) -> None:
    libraries_with_dev = [item["library"] for item in populated_result if item["version"] == "dev"]

    print(f"library_matrix={json.dumps(populated_result)}", file=f)
    print(f"libraries_with_dev={json.dumps(libraries_with_dev)}", file=f)
    print(f"desired_execution_time={600 if len(result) == 1 else 3600}", file=f)


if __name__ == "__main__":
    main()
