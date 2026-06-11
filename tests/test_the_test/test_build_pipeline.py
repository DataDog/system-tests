"""Tests for utils/ci/gitlab/build_pipeline.py — chunking, rendering, and CLI."""
import json
import re

import pytest
import yaml

from utils import scenarios
from utils.ci.gitlab.build_pipeline import build, main, noop_stub


MINIMAL_PARAMS = {
    "endtoend_defs": {
        "parallel_weblogs": [{"name": "flask"}],
        "parallel_jobs": [{"weblog": "flask", "scenarios": ["DEFAULT"], "weblog_build_required": True}],
    },
    "miscs": {"binaries_artifact": "flask-binaries"},
    "parametric": {"enable": False, "parallel_jobs": []},
}

BUILD_KWARGS = {"stage": "e2e", "ci_image": "myimage", "chunks": 3}


def write_params(tmp_path, *libs):
    for lib in libs:
        (tmp_path / f"params_{lib}.json").write_text(json.dumps(MINIMAL_PARAMS))


@scenarios.test_the_test
class Test_BuildPipeline:
    @pytest.mark.parametrize(
        "libs",
        [
            [],
            ["a"],
            ["a", "b"],
            ["a", "b", "c"],
            ["a", "b", "c", "d", "e", "f"],
        ],
    )
    def test_chunking_distribution(self, tmp_path, libs):
        write_params(tmp_path, *libs)
        out = tmp_path / "out"
        build(libs, tmp_path, out, **BUILD_KWARGS)

        # Expected round-robin assignment
        expected: dict[int, list[str]] = {i: [] for i in range(3)}
        for idx, lib in enumerate(libs):
            expected[idx % 3].append(lib)

        for i in range(3):
            chunk = yaml.safe_load((out / f"generated-pipeline-chunk-{i}.yml").read_text())
            if not expected[i]:
                assert "noop" in chunk, f"chunk {i} should be noop"
            else:
                jobs = {k: v for k, v in chunk.items() if isinstance(v, dict) and ("extends" in v or "script" in v)}
                assert jobs, f"chunk {i} should have jobs for {expected[i]}"

    def test_missing_params_exits_nonzero(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            main(["--stage", "e2e", "--libraries", "python", "--params-dir", str(tmp_path), "--ci-image", "x", "--output-dir", str(tmp_path / "out"), "--chunks", "3"])
        assert exc.value.code != 0

    def test_concatenation_no_duplicate_top_level_keys(self, tmp_path):
        """Two libs in same chunk (chunks=1) must not produce duplicate top-level YAML keys."""
        write_params(tmp_path, "python", "java")
        out = tmp_path / "out"
        build(["python", "java"], tmp_path, out, stage="e2e", ci_image="img", chunks=1)
        text = (out / "generated-pipeline-chunk-0.yml").read_text()
        for key in ("workflow:", "stages:", "include:"):
            count = len(re.findall(rf"^{re.escape(key)}", text, re.MULTILINE))
            assert count <= 1, f"duplicate top-level key '{key}' found {count} times"
