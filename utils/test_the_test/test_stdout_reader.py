import os
from utils._context.library_version import LibraryVersion
from utils.interfaces._logs.core import _LibraryStdout
from utils import context

context.execute_warmups = lambda *args, **kwargs: None


class Test_Main:
    def test_stdout_reader(self):
        """Test stdout reader"""

        context.library = LibraryVersion("java", "0.66.0")
        os.makedirs("logs/docker/weblog", exist_ok=True)
        with open("logs/docker/weblog/stdout.log", "w") as f:
            f.write("[dd.trace 2021-11-29 17:10:22:203 +0000] [main] DEBUG com.klass - some file\n")
            f.write("[dd.trace 2021-11-29 17:10:22:203 +0000] [main] INFO com.klass - AppSec initial 1.0.14\n")

        stdout = _LibraryStdout()

        stdout.assert_absence(r"System\.Exception")
        stdout.assert_presence(r"some.*file")
        stdout.assert_presence(r"AppSec initial \d+\.\d+\.\d+", level="INFO")

        stdout.assert_presence(r"some.*file", level="DEBUG")
        stdout.append_log_validation(lambda data: data["level"])

        stdout.wait()

        for v in stdout._validations:
            assert v.is_success, v
