# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re
import attr


def get_container_id(infos: list) -> str | None:
    for line in infos:
        info = _CGroupInfo.from_line(line)
        if info:
            return info.container_id

    return None


@attr.s(slots=True)
class _CGroupInfo:
    """CGroup class for container information parsed from a group cgroup file.

    This class is cloned from dd-trace-py implementation and serves as reference implementation
    for container id extraction.

    See https://github.com/DataDog/dd-trace-py/blob/1.x/ddtrace/internal/runtime/container.py
    """

    id = attr.ib(default=None)
    groups = attr.ib(default=None)
    path = attr.ib(default=None)
    container_id = attr.ib(default=None)
    controllers = attr.ib(default=None)
    pod_id = attr.ib(default=None)

    UUID_SOURCE_PATTERN = r"[0-9a-f]{8}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{12}"
    CONTAINER_SOURCE_PATTERN = r"[0-9a-f]{64}"
    TASK_PATTERN = r"[0-9a-f]{32}-\d+"

    LINE_RE = re.compile(r"^(\d+):([^:]*):(.+)$")
    POD_RE = re.compile(rf"pod({UUID_SOURCE_PATTERN})(?:\.slice)?$")
    CONTAINER_RE = re.compile(rf"(?:.+)?({UUID_SOURCE_PATTERN}|{CONTAINER_SOURCE_PATTERN}|{TASK_PATTERN})(?:\.scope)?$")

    @classmethod
    def from_line(cls, line: str) -> "_CGroupInfo | None":
        """Parse a new :class:`CGroupInfo` from the provided line
        :param line: A line from a cgroup file (e.g. /proc/self/cgroup) to parse information from
        :type line: str
        :returns: A :class:`CGroupInfo` object with all parsed data, if the line is valid, otherwise `None`
        :rtype: :class:`CGroupInfo` | None
        """
        # Clean up the line
        line = line.strip()

        # Ensure the line is valid
        match = cls.LINE_RE.match(line)
        if not match:
            return None

        id_, groups, path = match.groups()

        # Parse the controllers from the groups
        controllers = [c.strip() for c in groups.split(",") if c.strip()]

        # Break up the path to grab container_id and pod_id if available
        # e.g. /docker/<container_id>
        # e.g. /kubepods/test/pod<pod_id>/<container_id>
        parts = list(path.split("/"))

        # Grab the container id from the path if a valid id is present
        container_id = None
        if len(parts) != 0:
            match = cls.CONTAINER_RE.match(parts.pop())
            if match:
                container_id = match.group(1)

        # Grab the pod id from the path if a valid id is present
        pod_id = None
        if len(parts) != 0:
            match = cls.POD_RE.match(parts.pop())
            if match:
                pod_id = match.group(1)

        return cls(id=id_, groups=groups, path=path, container_id=container_id, controllers=controllers, pod_id=pod_id)
