from enum import StrEnum
from dataclasses import dataclass, replace
from pathlib import Path
import yaml


class BuildMode(StrEnum):
    none = "none"
    """ The weblog does not require any build step"""
    local = "local"
    prebuild = "prebuild"
    """ The weblog will be built in a dedicated job in the CI """


@dataclass
class WeblogMetaData:
    name: str
    library: str
    build_mode: BuildMode = BuildMode.prebuild
    framework_versions: list[str] | None = None
    artifact_name: str = ""
    """ not declared in the yml file, but populated later """

    def __post_init__(self):
        self.build_mode = BuildMode(self.build_mode)

    @property
    def require_build(self) -> bool:
        """The run_end_to_end job builds the weblog locally (weblog_build_required)."""
        return self.build_mode != BuildMode.none

    @property
    def require_prebuild(self) -> bool:
        """A dedicated build_end_to_end job pre-builds the weblog (parallel_weblogs)."""
        return self.build_mode == BuildMode.prebuild

    @staticmethod
    def _load_explicit_metadata() -> dict[str, "WeblogMetaData"]:
        with Path("utils/build/docker/weblog_metadata.yml").open() as f:
            data: dict = yaml.safe_load(f)

        result: dict[str, WeblogMetaData] = {}
        for name, kwargs in data.items():
            result[name] = WeblogMetaData(name=name, **kwargs)

        return result

    @staticmethod
    def load(library: str) -> list["WeblogMetaData"]:
        metadata = WeblogMetaData._load_explicit_metadata()
        result: list[WeblogMetaData] = []

        folder = Path(f"utils/build/docker/{library}")
        if folder.exists():  # some lib does not have any weblog
            names = [
                f.name.replace(".Dockerfile", "")
                for f in folder.iterdir()
                if f.suffix == ".Dockerfile" and ".base." not in f.name and f.is_file()
            ]

            for name in set(names + [w.name for w in metadata.values() if w.library == library]):
                item = WeblogMetaData(name=name, library=library) if name not in metadata else metadata[name]

                # integration-framework weblogs fan out into one weblog per version;
                # all other weblogs map to a single weblog.
                if item.framework_versions:
                    for version in item.framework_versions:
                        sub_item = replace(item, name=f"{name}@{version}")
                        result.append(sub_item)
                else:
                    result.append(item)

        return result


if __name__ == "__main__":
    x = WeblogMetaData.load("python")
    from pprint import pprint

    pprint(x)  # noqa: T203
