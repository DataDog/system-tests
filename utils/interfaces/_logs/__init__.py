if __name__ == "__main__":

    def test_something():
        """Test something"""

        from utils.interfaces._logs.core import _LibraryDotnetManaged, _LibraryStdout
        from utils import context

        stdout = _LibraryStdout() if context.library != "dotnet" else _LibraryDotnetManaged()

        stdout.assert_absence(r"System\.Exception")

        # stdout.assert_presence(r"AppSec loaded \d+ rules from file <bundled config>", level="INFO")
        stdout.assert_presence(r"Loaded rule: crs-942-160 - Detects blind sqli tests using sleep", level="DEBUG")

        stdout.append_log_validation(lambda data: data["level"])
        stdout.__test__()

    test_something()
