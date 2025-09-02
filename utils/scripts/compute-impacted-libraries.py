import argparse
import json
import os
import re
import sys
from typing import Any, TextIO

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

lambda_libraries = ["python_lambda"]

libraries = (
    "cpp|cpp_httpd|cpp_nginx|dotnet|golang|java|nodejs|php|python|ruby|java_otel|python_otel|nodejs_otel|python_lambda"
)


def get_impacted_libraries(modified_file: str) -> list[str]:
    """Return the list of impacted libraries by this file"""
    if modified_file.endswith((".md", ".rdoc", ".txt")):
        # modification in documentation file
        return []

    files_with_no_impact = [
        "utils/scripts/compute-impacted-libraries.py",
        ".github/workflows/compute-impacted-libraries.yml",
    ]
    if modified_file in files_with_no_impact:
        return []

    lambda_proxy_patterns = [
        "utils/build/docker/lambda_proxy/.+",
        "utils/build/docker/lambda-proxy.Dockerfile",
    ]
    for pattern in lambda_proxy_patterns:
        if re.match(pattern, modified_file):
            return lambda_libraries

    patterns = [
        rf"^manifests/({libraries})\.",
        rf"^utils/build/docker/({libraries})/",
        rf"^lib-injection/build/docker/({libraries})/",
        rf"^utils/build/build_({libraries})_base_images.sh",
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
        rebuild_lambda_proxy = False
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

            if file in ("utils/build/docker/lambda_proxy/pyproject.toml", "utils/build/docker/lambda-proxy.Dockerfile"):
                rebuild_lambda_proxy = True

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

    libraries_with_dev = [item["library"] for item in populated_result if item["version"] == "dev"]
    outputs = {
        "library_matrix": populated_result,
        "libraries_with_dev": libraries_with_dev,
        "desired_execution_time": 600 if len(result) == 1 else 3600,
        "rebuild_lambda_proxy": rebuild_lambda_proxy,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            print_github_outputs(outputs, f)
    else:
        print_github_outputs(outputs, sys.stdout)


def print_github_outputs(outputs: dict[str, Any], f: TextIO) -> None:
    for name, value in outputs.items():
        print(f"{name}={json.dumps(value)}", file=f)


if __name__ == "__main__":
    main()
