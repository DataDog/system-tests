import json
import os
import re
import sys


def main() -> None:
    libraries = "cpp|cpp_httpd|cpp_nginx|dotnet|golang|java|nodejs|php|python|ruby|java_otel|python_otel|nodejs_otel"
    result = set()

    # do not include otel in system-tests CI by default, as the staging backend is not stable enough
    # all_libraries = {
    #   "cpp", "dotnet", "golang", "java", "nodejs", "php", "python", "ruby", "java_otel", "python_otel", "nodejs_otel"
    # }
    all_libraries = {"cpp", "cpp_httpd", "cpp_nginx", "dotnet", "golang", "java", "nodejs", "php", "python", "ruby"}

    if os.environ.get("GITHUB_REF") == "refs/heads/main":
        print("Merge commit to main => run all libraries")
        result |= all_libraries

    elif os.environ.get("GITHUB_EVENT_NAME") in ("schedule", "push"):
        print("Scheduled job => run all libraries")
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

            if match:
                library = match[2]
                if user_choice is not None and library != user_choice:
                    print(f"You've selected {user_choice}, but the modified file {file} impacts {library}.")
                    sys.exit(1)

                result.add(library)
            elif file.startswith("tests/"):
                if user_choice is None:
                    result |= all_libraries

            elif user_choice is not None:
                print(f"File {file} is modified, and it may impact all libraries.")
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
