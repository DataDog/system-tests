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


class WeblogCategory(StrEnum):
    """Used to connect scenario and weblogs"""

    dd_trace = "dd_trace"
    """ Basic dd-trace instrumentation of an HTTP app """

    dd_trace_graphql = "dd_trace_graphql"
    """ dd-trace instrumentation of an GraphQL app """

    dd_trace_lambda = "dd_trace_lambda"
    """ dd-trace inside a lamnda function """

    dd_trace_frameworks = "dd_trace_frameworks"
    """ dd-trace instrumentation of multi-language framneworks (mostly AI) """

    open_telemetry = "open_telemetry"
    """ Open Telemetry library """

    parametric = "parametric"
    """ Weblog shipping a dd-trace library with an interface dedicated to PARAMETRIC scenario """


class ContainerPorts(IntEnum):
    """Host ports used by tested containers"""

    vcr_cassettes = 8300
