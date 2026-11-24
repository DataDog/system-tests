from pathlib import Path

from utils import pytest
from utils import scenarios
from utils.scripts import generate_public_registry_pipeline as generator

MIRROR = "registry.ddbuild.io/system-tests/mirror"


def _write_mirror_lock(path: Path) -> Path:
    path.write_text(
        f"""\
version: 1
images:
  alpine:3.22:
    digest: sha256:alpine
    target: {MIRROR}/alpine:3.22
    tag: '3.22'
  datadog/system-tests:proxy-v1:
    digest: sha256:proxy
    target: {MIRROR}/datadog/system-tests:proxy-v1
    tag: proxy-v1
""",
        encoding="utf-8",
    )
    return path


@scenarios.test_the_test
class Test_GeneratePublicRegistryPipeline:
    def test_wanted_images(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            generator,
            "load_base_image_lock",
            lambda: {"system_tests_base_x": "datadog/system-tests:x.base-123456789abc"},
        )

        images = generator.wanted_images(_write_mirror_lock(tmp_path / "mirror_images.lock.yaml"))

        assert images == {
            "x.base-123456789abc": (f"{MIRROR}/datadog/system-tests:x.base-123456789abc", None),
            "proxy-v1": (f"{MIRROR}/datadog/system-tests:proxy-v1", "sha256:proxy"),
        }

    def test_missing_images(self, monkeypatch: pytest.MonkeyPatch):
        published = {"present.base-1": "sha256:any", "same": "sha256:same", "moved": "sha256:old"}
        monkeypatch.setattr(generator, "published_digest", published.get)

        missing = generator.missing_images(
            {
                "absent.base-1": ("src/absent", None),
                "present.base-1": ("src/present", None),
                "same": ("src/same", "sha256:same"),
                "moved": ("src/moved", "sha256:new"),
            }
        )

        assert missing == {"absent.base-1": "src/absent", "moved": "src/moved"}

    def test_child_pipeline(self):
        pipeline = generator.child_pipeline({"proxy-v1": f"{MIRROR}/datadog/system-tests:proxy-v1"})

        assert pipeline == {
            "publish_proxy-v1": {
                "trigger": {"project": "DataDog/public-images", "branch": "main", "strategy": "depend"},
                "variables": {
                    "IMG_SOURCES": f"{MIRROR}/datadog/system-tests:proxy-v1",
                    "IMG_DESTINATIONS": "system-tests:proxy-v1",
                    "IMG_REGISTRIES": "prod",
                    "IMG_MERGE_STRATEGY": "none",
                    "IMG_SIGNING": "false",
                },
            }
        }

    def test_child_pipeline_without_images_has_a_job(self):
        assert list(generator.child_pipeline({})) == ["nothing_to_publish"]
