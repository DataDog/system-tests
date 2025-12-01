from pathlib import Path
from utils import scenarios
from utils.interfaces._logs import _LibraryStdout


@scenarios.test_the_test
class Test_Main:
    def test_stdout_reader(self):
        """Test stdout reader"""

        Path("logs_test_the_test/docker/weblog").mkdir(parents=True, exist_ok=True)
        with open("logs_test_the_test/docker/weblog/stdout.log", "w", encoding="utf-8") as f:
            f.write("[dd.trace 2021-11-29 17:10:22:203 +0000] [main] DEBUG com.klass - some file\n")
            f.write("[dd.trace 2021-11-29 17:10:22:203 +0000] [main] INFO com.klass - AppSec initial 1.0.14\n")

        stdout = _LibraryStdout()
        stdout.configure(scenarios.test_the_test.host_log_folder, replay=False)
        stdout.init_patterns(scenarios.test_the_test.library)

        stdout.load_data()

        stdout.assert_absence(r"System\.Exception")
        stdout.assert_presence(r"some.*file")
        stdout.assert_presence(r"AppSec initial \d+\.\d+\.\d+", level="INFO")

        stdout.assert_presence(r"some.*file", level="DEBUG")
