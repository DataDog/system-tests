import os
import pytest
from utils.interfaces._logs import _LibraryStdout


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


class Test_Main:
    def test_stdout_reader(self):
        """Test stdout reader"""

        os.makedirs("logs_test_the_test/docker/weblog", exist_ok=True)
        with open("logs_test_the_test/docker/weblog/stdout.log", "w", encoding="utf-8") as f:
            f.write("[dd.trace 2021-11-29 17:10:22:203 +0000] [main] DEBUG com.klass - some file\n")
            f.write("[dd.trace 2021-11-29 17:10:22:203 +0000] [main] INFO com.klass - AppSec initial 1.0.14\n")

        stdout = _LibraryStdout()
        stdout.configure(False)

        stdout.load_data()

        stdout.assert_absence(r"System\.Exception")
        stdout.assert_presence(r"some.*file")
        stdout.assert_presence(r"AppSec initial \d+\.\d+\.\d+", level="INFO")

        stdout.assert_presence(r"some.*file", level="DEBUG")
