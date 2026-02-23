from enum import IntEnum


class ContainerPorts(IntEnum):
    """Host ports used by tested containers"""

    vcr_cassettes = 8300
