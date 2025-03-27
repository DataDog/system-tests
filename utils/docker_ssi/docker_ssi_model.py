class RuntimeInstallableVersion:
    """Encapsulates information of the version of the language that can be installed automatically"""

    def __init__(self, version_id, version) -> None:
        self.version_id = version_id
        self.version = version


class DockerImage:
    """Encapsulates information of the docker image"""

    def __init__(self, internal_name, tag, platform) -> None:
        # Try to set the same name as utils/_context/virtual_machines.py
        self.internal_name = internal_name
        self.tag = tag
        self.platform = platform
        self.runtime_versions: list[str] = []

    def with_allowed_runtime_versions(self, runtime_versions):
        self.runtime_versions = runtime_versions
        return self

    def add_allowed_runtime_version(self, runtime_version):
        self.runtime_versions.append(runtime_version)
        return self

    def tag_name(self):
        return self.tag.rsplit("/", 1)[-1]

    def name(self):
        return self.tag.replace(":", "_").replace("/", "_").replace(".", "_") + "_" + self.platform.replace("/", "_")


class WeblogDescriptor:
    """Encapsulates information of the weblog: name, library and
    supported images with the supported installable runtime versions
    """

    # see utils._features to check ids
    def __init__(self, name, library, supported_images):
        self.name = name
        self.library = library
        self.supported_images = supported_images

    def get_matrix(self):
        matrix_combinations = []
        for image in self.supported_images:
            if not image.runtime_versions:
                matrix_combinations.append(
                    {
                        "weblog": self.name,
                        "base_image": image.tag,
                        "arch": image.platform,
                        "installable_runtime": "''",
                        "unique_name": self.clean_name(f"{self.name}_{image.tag}_{image.platform}"),
                    },
                )
            else:
                for runtime_version in image.runtime_versions:
                    matrix_combinations.append(
                        {
                            "weblog": self.name,
                            "base_image": image.tag,
                            "arch": image.platform,
                            "installable_runtime": runtime_version.version,
                            "unique_name": self.clean_name(
                                f"{self.name}_{image.tag}_{image.platform}_{runtime_version.version_id}"
                            ),
                        }
                    )
        return matrix_combinations

    def clean_name(self, tag_to_clean):
        return tag_to_clean.replace(":", "_").replace("/", "_").replace(".", "_").replace("-", "_").lower()
