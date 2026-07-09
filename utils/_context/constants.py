from enum import StrEnum, IntEnum


class WeblogBuildMode(StrEnum):
    """Describe how a weblog should be built"""

    none = "none"
    """ The weblog does not require any build step"""

    local = "local"
    """ The weblog has a fully baked base image, so the build step is extra light,
    and does not requires a full job in the CI"""

    prebuild = "prebuild"
    """ The weblog will be built in a dedicated job in the CI """


class ContainerPorts(IntEnum):
    """Host ports used by tested containers"""

    vcr_cassettes = 8300
