from .const import LIBRARIES
from .core import update_manifest
from .test_artifact import parse_artifact_data
from .manifest_editor import ManifestEditor


def main() -> None:
    manifest_editor = ManifestEditor()
    test_data = parse_artifact_data("data/", LIBRARIES)
    update_manifest(manifest_editor, test_data)
    manifest_editor.write()


if __name__ == "__main__":
    main()
