from typing import Any
from utils.dd_constants import Capabilities


def human_readable_capabilities(caps: int) -> tuple[Any, ...]:
    return tuple(c.name for c in Capabilities if caps >> c & 1)
