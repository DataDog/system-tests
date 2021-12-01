import json
from pathlib import Path
import logging


class Logs(list):
    def write(self, line):
        self.append(line)

    def __str__(self):
        return "\n".join([l.strip() for l in self])


logs = Logs()


def create_context():
    print("Create context")

    Path("logs/docker/weblog/").mkdir(exist_ok=True, parents=True)

    def build_docker_info(name, env):
        data = [{"Config": {"Env": env}}]
        json.dump(data, open(f"logs/{name}_image.json", "w"))

    build_docker_info("agent", {})
    build_docker_info("weblog", ["SYSTEM_TESTS_LIBRARY=java", "SYSTEM_TESTS_LIBRARY_VERSION=0.66.0"])

    from utils.tools import logger

    logger.addHandler(logging.StreamHandler(stream=logs))


def test_decorators():
    from utils._decorators import bug, released, rfc, irrelevant

    def is_skipped(item):
        if hasattr(item, "pytestmark"):
            for mark in item.pytestmark:
                if mark.name == "skip":
                    return True

        return False

    @bug(library="java", reason="test")
    def test_function():
        pass

    assert is_skipped(test_function)
    assert "test_function function, known bug: test => skipped\n" in logs

    @bug(library="java", reason="test")
    class Test_Class:
        @irrelevant(library="java")
        def test_method(self):
            pass

        @irrelevant(library="nodejs")
        def test_method2(self):
            pass

    assert is_skipped(Test_Class)
    assert is_skipped(Test_Class.test_method)
    assert not is_skipped(Test_Class.test_method2)
    assert "test_method function, not relevant => skipped\n" in logs
    assert "Test_Class class, known bug: test => skipped\n" in logs

    @rfc("A link")
    @released(java="99.99")
    class Test2:
        pass

    assert "Test2 class, missing feature: release version is 99.99 => skipped\n" in logs
    assert Test2().__released__ == "99.99"
    assert Test2().__rfc__ == "A link"

    print("Test decorators OK")


def test_context():
    from utils import context

    assert context.library == "java"
    assert context.library == "java@0.66.0"
    assert context.weblog_variant is None
    assert context.sampling_rate is None
    assert context.waf_rule_set == "0.0.1"
    print("Test context OK")


def test_version():
    from utils._context.library_version import Version

    v = Version("1.0")

    assert v == "1.0"
    assert v != "1.1"

    assert v <= "1.1"
    assert v <= "1.0"
    assert "1.1" >= v
    assert "1.0" >= v

    assert v < "1.1"
    assert "1.1" > v

    assert v >= "0.9"
    assert v >= "1.0"
    assert "0.9" <= v
    assert "1.0" <= v

    assert v > "0.9"
    assert "0.9" < v

    v = Version("0.53.0.dev70+g494e6dc0")

    assert v == "0.53.0.dev70+g494e6dc0"

    assert Version("1.31.1") < "v1.34.1-0.20211116150256-dd5b7c8a7caf"
    assert "1.31.1" < Version("v1.34.1-0.20211116150256-dd5b7c8a7caf")
    assert Version("1.31.1") < Version("v1.34.1-0.20211116150256-dd5b7c8a7caf")

    v = Version("  * ddtrace (0.53.0.appsec.180045)", "ruby")
    assert v == Version("0.53.0")

    print("Test Version class OK")


def test_library_version():
    from utils._context.library_version import LibraryVersion

    v = LibraryVersion("p")
    assert v == "p"
    assert v != "u"

    v = LibraryVersion("p", "1.0")

    assert v == "p@1.0"
    assert v == "p"
    assert v != "p@1.1"
    assert v != "u"

    assert v <= "p@1.1"
    assert v <= "p@1.0"
    assert "p@1.1" >= v
    assert "p@1.0" >= v

    assert v < "p@1.1"
    assert "p@1.1" > v

    assert v >= "p@0.9"
    assert v >= "p@1.0"
    assert "p@0.9" <= v
    assert "p@1.0" <= v

    assert v > "p@0.9"
    assert "p@0.9" < v

    assert (v <= "u@1.0") is False
    assert (v >= "u@1.0") is False

    assert ("u@1.0" <= v) is False
    assert ("u@1.0" >= v) is False

    v = LibraryVersion("p")

    assert ("u@1.0" == v) is False
    assert ("u@1.0" <= v) is False

    v = LibraryVersion("python", "0.53.0.dev70+g494e6dc0")

    assert v == "python@0.53.0.dev70+g494e6dc0"

    print("Test LibraryVersion class OK")


def test_stdout_reader():
    """ Test stdout reader """

    from utils.interfaces._logs.core import _LibraryStdout

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

    print("Test log reader ok")


def test_message_collector():
    """ Test magic message collector """
    from utils.interfaces._core import BaseValidation

    assert BaseValidation("Inline message").message == "Inline message"
    assert BaseValidation().message == "Test magic message collector", repr(BaseValidation().message)

    class Test_Class:
        """ A test class """

        def test_A(self):
            assert BaseValidation("Inline message").message == "Inline message"
            assert BaseValidation().message == "A test class"

        def test_B(self):
            """ A test method """
            assert BaseValidation("Inline message").message == "Inline message"
            assert BaseValidation().message == "A test method"

    Test_Class().test_A()
    Test_Class().test_B()

    print("Test message magic collector OK")


create_context()

test_decorators()
test_context()
test_version()
test_library_version()
test_stdout_reader()
test_message_collector()

print("All good, you can have a 🍺")
