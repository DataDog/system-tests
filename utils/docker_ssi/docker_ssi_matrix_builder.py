import os
import json


def get_github_matrix(library):
    try:
        from utils.docker_ssi.docker_ssi_definitions import ALL_WEBLOGS
    except ImportError:
        from docker_ssi_definitions import ALL_WEBLOGS

    """ Matrix that will be used in the github workflow """
    tests = []
    github_matrix = {"include": []}

    filtered = [weblog for weblog in ALL_WEBLOGS if weblog.library == library]
    for weblog in filtered:
        weblog_matrix = weblog.get_matrix()
        if not weblog_matrix:
            continue
        tests = tests + weblog_matrix

    github_matrix["include"] = tests
    return github_matrix


def main():
    if not os.getenv("TEST_LIBRARY"):
        raise ValueError("TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby")
    github_matrix = get_github_matrix(os.getenv("TEST_LIBRARY"))
    print(json.dumps(github_matrix))


if __name__ == "__main__":
    main()
