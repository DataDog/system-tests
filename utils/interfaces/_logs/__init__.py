# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

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
