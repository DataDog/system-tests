"""Libraries, weblogs and scenarios run by the GitLab end-to-end pipeline, used by compute_libraries_and_scenarios.py.

Modifying this file runs the whole CI (see libraries_and_scenarios_rules.yml).
"""

# Libraries run by GitLab end-to-end on PRs. The value is either None, to run the scenarios selected from the diff
# on every weblog of the library, or a {weblog: [scenario or scenario group, ...]} map, to run only these
# weblogs/scenarios when the library is activated.
GITLAB_PR_LIBRARIES: dict[str, dict[str, list[str]] | None] = {
    "c": None,
    # THREAD_CONTEXT_SHARING needs a dedicated runner pool: checks that this setup works. One weblog is enough.
    "php": {"apache-mod-8.0": ["THREAD_CONTEXT_SHARING"]},
    # GitLab runs containers on the default bridge network: checks that the mocked backend network aliases work there
    "python": {
        "flask-poc": [
            "APM_TRACING_E2E_SINGLE_SPAN",
            "FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS",
            "FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS_DIRECT",
            "FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS_SERVERLESS",
        ]
    },
}

# Libraries run by GitLab end-to-end on main pushes, same format as GITLAB_PR_LIBRARIES
GITLAB_MAIN: dict[str, dict[str, list[str]] | None] = {
    "php": GITLAB_PR_LIBRARIES["php"],
    "python": None,
}
