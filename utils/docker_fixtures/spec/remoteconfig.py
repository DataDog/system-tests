from utils.dd_constants import Capabilities


def human_readable_capabilities(caps: int) -> set[Capabilities]:
    return {c for c in Capabilities if caps >> c & 1}
