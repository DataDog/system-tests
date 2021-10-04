import os
import re


def main():
    all_files = []

    for folder in ("tests", ".github", "utils", "interfaces"):
        for root, _, files in os.walk(folder):
            for f in files:
                if f.endswith(".py") or f.endswith(".yml"):
                    all_files.append(os.path.join(root, f))

    jiras = set()
    for file in all_files:
        content = "".join(open(file, "r").readlines())
        for result in re.finditer("(ARB|ANJS|AJA|ANET|APHP|APY|AGO|SQR)-(\d+)", content):
            jiras.add(result.group())

    for jira in sorted(jiras):
        print(f"https://sqreen.atlassian.net/browse/{jira}")


if __name__ == "__main__":
    main()
