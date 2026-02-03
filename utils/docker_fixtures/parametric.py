from enum import Enum
from typing import TypedDict, NotRequired


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class Link(TypedDict):
    parent_id: int
    attributes: NotRequired[dict]
