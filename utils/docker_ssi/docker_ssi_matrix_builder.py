import os
import json


def get_github_matrix(library):
    """ Matrix that will be used in the github workflow """
    # We can call this function from a script on at runtime
    try:
        from utils.docker_ssi.docker_ssi_definitions import ALL_WEBLOGS
    except ImportError:
        from docker_ssi_definitions import ALL_WEBLOGS

    tests = []
    github_matrix = {"include": []}

    filtered = [weblog for weblog in ALL_WEBLOGS if weblog.library == library]
    for weblog in filtered:
        weblog_matrix = weblog.get_matrix()
        if not weblog_matrix:
            continue
        _configure_github_runner(weblog_matrix)
        tests = tests + weblog_matrix

    github_matrix["include"] = tests
    return github_matrix


def _configure_github_runner(weblog_matrix):
    """ We need to select the github runned based on the architecture of the images that we want to test"""
    for weblog in weblog_matrix:
        if weblog["arch"] == "linux/amd64":
            weblog["github_runner"] = "ubuntu-latest"
        else:
            weblog["gibhub_runner"] = "arm-8core-linux"


def main():
    if not os.getenv("TEST_LIBRARY"):
        raise ValueError("TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby")
    github_matrix = get_github_matrix(os.getenv("TEST_LIBRARY"))
    print(json.dumps(github_matrix))


if __name__ == "__main__":
    main()
