class RuntimeVersions:
    """ Encapsulates information of the version of the language """

    def __init__(self, version_id, version) -> None:
        self.version_id = version_id
        self.version = version


class DockerImage:
    """ Encapsulates information of the docker image """

    def __init__(self, tag, platform) -> None:
        self.tag = tag
        self.platform = platform
        self.runtime_versions = []

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
    """ Encapsulates information of the weblog: name, library and 
        supported images with the supported runtime versions """

    def __init__(self, name, library, supported_images):
        self.name = name
        self.library = library
        self.supported_images = supported_images

    def get_matrix(self):
        matrix_combinations = []
        for image in self.supported_images:
            if not image.runtime_versions:
                matrix_combinations.append(
                    {"weblog": self.name, "base_image": image.tag, "arch": image.platform, "runtime": ""}
                )
            else:
                for runtime_version in image.runtime_versions:
                    matrix_combinations.append(
                        {
                            "weblog": self.name,
                            "base_image": image.tag,
                            "arch": image.platform,
                            "runtime": runtime_version.version,
                            "unique_name": self.clean_name(
                                f"{self.name}_{image.tag}_{image.platform}_{runtime_version.version_id}"
                            ),
                        }
                    )
        return matrix_combinations

    def clean_name(self, str):
        return str.replace(":", "_").replace("/", "_").replace(".", "_").replace("-", "_").lower()
