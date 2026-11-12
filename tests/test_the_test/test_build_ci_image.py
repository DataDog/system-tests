"""Tests of the hardcoded image checks in utils/ci/gitlab/build_ci_image.py."""

import re
from pathlib import Path

from utils import features, pytest, scenarios
from utils.ci.gitlab import build_ci_image


def _hardcoded(variable: str, file: str) -> str:
    match = re.search(rf'{variable}: "([^"]+)"', Path(file).read_text(encoding="utf-8"))
    assert match is not None, f"{variable} is not in {file}"
    return match.group(1)


@features.not_reported
@scenarios.test_the_test
class Test_BuildCiImage:
    def test_hardcoded_images_match_the_computed_tags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for variable, file in (("CI_IMAGE", "utils/ci/gitlab/main.yml"), ("REVIEW_LEARNING_IMAGE", ".gitlab-ci.yml")):
            monkeypatch.setenv(variable, _hardcoded(variable, file))
        build_ci_image._check_hardcoded_images(build_ci_image._compute_tags())  # noqa: SLF001

    def test_review_learning_tag_only_follows_its_dockerfile(self) -> None:
        tags = build_ci_image._compute_tags()  # noqa: SLF001
        dockerfile = build_ci_image.DOCKER_DIR / "review-learning.Dockerfile"
        assert tags["review-learning"] == build_ci_image._sha256_tag(dockerfile)  # noqa: SLF001

    def test_every_mismatch_is_reported_before_the_failure(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("CI_IMAGE", "registry/ci-runner:old")
        monkeypatch.setenv("REVIEW_LEARNING_IMAGE", "registry/review-learning:old")
        with pytest.raises(SystemExit):
            build_ci_image._check_hardcoded_images(build_ci_image._compute_tags())  # noqa: SLF001
        output = capsys.readouterr().out
        assert "CI_IMAGE" in output
        assert "REVIEW_LEARNING_IMAGE" in output
        assert "sha256sum" in output
