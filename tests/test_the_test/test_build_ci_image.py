"""Tests of utils/ci/gitlab/build_ci_image.py. They never build or push an image."""

from utils import features, pytest, scenarios
from utils.ci.gitlab import build_ci_image


def _ci_image() -> str:
    return f"{build_ci_image.REGISTRY}/ci-runner:{build_ci_image._ci_runner_tag()}"  # noqa: SLF001


@features.not_reported
@scenarios.test_the_test
class Test_BuildCiImage:
    def test_check_only_needs_only_ci_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # dd-trace-php runs this exact command in its own pipeline, where only CI_IMAGE exists.
        monkeypatch.setenv("CI_IMAGE", _ci_image())
        monkeypatch.delenv("REVIEW_LEARNING_IMAGE", raising=False)
        monkeypatch.setattr("sys.argv", ["build_ci_image.py", "--check-only"])
        build_ci_image.main()

    def test_check_only_fails_on_a_wrong_ci_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CI_IMAGE", f"{build_ci_image.REGISTRY}/ci-runner:wrong")
        monkeypatch.setattr("sys.argv", ["build_ci_image.py", "--check-only"])
        with pytest.raises(SystemExit) as error:
            build_ci_image.main()
        assert error.value.code == 1

    def test_full_run_needs_every_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CI_IMAGE", _ci_image())
        monkeypatch.delenv("REVIEW_LEARNING_IMAGE", raising=False)
        monkeypatch.setattr(build_ci_image, "_build_missing", lambda _names, _tags: None)
        monkeypatch.setattr("sys.argv", ["build_ci_image.py"])
        with pytest.raises(SystemExit) as error:
            build_ci_image.main()
        assert error.value.code == 1
