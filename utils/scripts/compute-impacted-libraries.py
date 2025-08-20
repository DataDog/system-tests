import json
import os
import re
import sys


def main() -> None:
    libraries = "cpp|cpp_httpd|cpp_nginx|dotnet|golang|java|nodejs|php|python|ruby|java_otel|python_otel|nodejs_otel|python_lambda"  # noqa: E501
    result = set()

    # do not include otel in system-tests CI by default, as the staging backend is not stable enough
    # all_libraries = {
    #   "cpp", "dotnet", "golang", "java", "nodejs", "php", "python", "ruby", "java_otel", "python_otel", "nodejs_otel"
    # }
    all_libraries = {
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
    }

    if os.environ.get("GITHUB_EVENT_NAME", "pull_request") != "pull_request":
        print("Not in PR => run all libraries")
        result |= all_libraries

    else:
        pr_title = os.environ.get("GITHUB_PR_TITLE", "").lower()
        match = re.search(rf"^\[({libraries})(?:@([^\]]+))?\]", pr_title)
        user_choice = None
        if match:
            print(f"PR title matchs => run {match[1]}")
            user_choice = match[1]
            result.add(user_choice)

        print("Inspect modified files to determine impacted libraries...")

        with open("modified_files.txt", "r", encoding="utf-8") as f:
            modified_files: list[str] = f.readlines()

        for file in modified_files:
            match = re.search(rf"^(manifests|utils/build/docker|lib-injection/build/docker)/({libraries})(\./)", file)

            if user_choice is not None:
                # user let the script pick impacted libraries
                if match:
                    result.add(match[2])
                else:
                    result |= all_libraries
            else:  # noqa: PLR5501
                # user specified a library in the PR title
                if match:
                    if match[2] != user_choice:
                        print(f"File {file} is modified, and it may impact {match[2]}.")
                        sys.exit(1)
                elif file.startswith("tests/"):
                    # modification in tests files are complex, trust user
                    ...
                else:
                    print(f"File {file} is modified, but it may impact all libraries")
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

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        print(f"library_matrix={json.dumps(populated_result)}", file=fh)
        print(
            f"libraries_with_dev={json.dumps(libraries_with_dev)}",
            file=fh,
        )
        print(f"desired_execution_time={600 if len(result) == 1 else 3600}", file=fh)


if __name__ == "__main__":
    main()
