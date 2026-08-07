from dataclasses import dataclass, replace, field
from pathlib import Path
import yaml

from utils.scripts.base_image import base_image_ref
from .constants import WeblogBuildMode, WeblogCategory


@dataclass
class WeblogMetaData:
    name: str
    library: str
    build_mode: WeblogBuildMode = WeblogBuildMode.prebuild
    framework_versions: list[str] | None = None
    artifact_name: str = ""
    """ not declared in the yml file, but populated later """

    supported_scenarios: list[str] = field(default_factory=list)
    excluded_scenarios: list[str] = field(default_factory=list)

    categories: list[WeblogCategory] = field(default_factory=list)

    def __post_init__(self):
        # cast enums
        self.build_mode = WeblogBuildMode(self.build_mode)
        self.categories = [WeblogCategory[category] for category in self.categories]

    @property
    def require_build(self) -> bool:
        """The run_end_to_end job builds the weblog locally (weblog_build_required)."""
        return self.build_mode != WeblogBuildMode.none

    @property
    def base_image_tag(self) -> str | None:
        """system-tests base image the weblog Dockerfile builds FROM (see base_image.py)."""
        dockerfile = Path(f"utils/build/docker/{self.library}/{self.name}.Dockerfile")
        if not dockerfile.exists():
            return None
        return base_image_ref(dockerfile.read_text())

    @staticmethod
    def _load_explicit_metadata(library: str) -> dict[str, "WeblogMetaData"]:
        path = Path(f"utils/build/docker/{library}/weblog_metadata.yml")
        if not path.exists():
            return {}

        with path.open() as f:
            data: dict = yaml.safe_load(f) or {}

        return {name: WeblogMetaData(name=name, library=library, **kwargs) for name, kwargs in data.items()}

    @staticmethod
    def load(library: str) -> list["WeblogMetaData"]:
        metadata = WeblogMetaData._load_explicit_metadata(library)
        result: list[WeblogMetaData] = []

        folder = Path(f"utils/build/docker/{library}")
        if folder.exists():  # some lib does not have any weblog
            names = [
                f.name.replace(".Dockerfile", "")
                for f in folder.iterdir()
                if f.suffix == ".Dockerfile" and ".base." not in f.name and f.is_file()
            ]
        else:
            names = []

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

    def support_scenario(self, scenario_name: str, weblog_categories: list[WeblogCategory]) -> bool:
        if scenario_name in self.excluded_scenarios:
            return False

        if scenario_name in self.supported_scenarios:
            return True

        return any(category in self.categories for category in weblog_categories)
