# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc validations"""


def validate_process_tags(process_tags: str):
    # entrypoint name and workdir can always be defined.
    if "entrypoint.name:" not in process_tags:
        raise ValueError(f"No entrypoint.name defined in process tags. Current: {process_tags}")
    if "entrypoint.workdir:" not in process_tags:
        raise ValueError(f"No entrypoint.workdir defined in process tags. Current: {process_tags}")


def validate_process_tags_svc(process_tags: str):
    validate_process_tags(process_tags)
    if not ("svc.auto:" in process_tags or "svc.user" in process_tags):
        raise ValueError(f"""No default service name indication in process tags.
            Expected either svc.auto or svc.user. Current: {process_tags}""")
