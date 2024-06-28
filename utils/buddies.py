from collections import defaultdict
from utils._weblog import _Weblog


class _Buddy(_Weblog):
    def __init__(self, port, language, domain="localhost"):
        super().__init__()

        self.port = port
        self.domain = domain

        self.responses = defaultdict(list)
        self.current_nodeid = "not used"
        self.replay = False
        self.language = language


python_buddy = _Buddy(9001, "python")
nodejs_buddy = _Buddy(9002, "nodejs")
java_buddy = _Buddy(9003, "java")
ruby_buddy = _Buddy(9004, "ruby")
golang_buddy = _Buddy(9005, "golang")
python_otel_buddy = _Buddy(9006, "python-otel")
