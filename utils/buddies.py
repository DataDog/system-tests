from utils._weblog import _Weblog
from enum import IntEnum


class BuddyHostPorts(IntEnum):
    """On which port on host buddy is accessible ?"""

    python = 9001
    nodejs = 9002
    java = 9003
    ruby = 9004
    golang = 9005


class _Buddy(_Weblog):
    def __init__(self, port: int, language: str, domain: str = "localhost"):
        super().__init__()

        self.port = port
        self.domain = domain
        self.language = language


python_buddy = _Buddy(BuddyHostPorts.python, "python")
nodejs_buddy = _Buddy(BuddyHostPorts.nodejs, "nodejs")
java_buddy = _Buddy(BuddyHostPorts.java, "java")
ruby_buddy = _Buddy(BuddyHostPorts.ruby, "ruby")
golang_buddy = _Buddy(BuddyHostPorts.golang, "golang")
