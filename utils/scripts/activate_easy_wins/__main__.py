import argparse
from os import environ
from pathlib import Path
from .const import ARTIFACT_URL, LIBRARIES
from .core import update_manifest
from .test_artifact import parse_artifact_data, pull_artifact
from .manifest_editor import ManifestEditor


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate easy wins from test artifacts")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip downloading the artifact and use existing data directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only display a summary of changes without writing anything to disk",
    )
    args = parser.parse_args()

    manifest_editor = ManifestEditor()

    if not args.no_download:
        token = environ["GITHUB_TOKEN"]
        pull_artifact(ARTIFACT_URL, token, Path("data"))

    test_data, weblogs = parse_artifact_data(Path("data/"), LIBRARIES)
    print(weblogs)
    return
    update_manifest(manifest_editor, test_data)

    if not args.dry_run:
        manifest_editor.write()


if __name__ == "__main__":
    main()
