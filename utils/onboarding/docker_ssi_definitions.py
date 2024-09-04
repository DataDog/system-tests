LINUX_AMD64 = "linux/amd64"
LINUX_ARM64 = "linux/arm64"


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

    def tag_name(self):
        return self.tag.rsplit("/", 1)[-1]

    def name(self):
        return self.tag.replace(":", "_").replace("/", "_").replace(".", "_") + "_" + self.platform.replace("/", "_")


class SupportedImages:
    """ All supported images """

    UBUNTU_22_AMD64 = DockerImage("ubuntu:22.04", LINUX_AMD64)
    UBUNTU_22_ARM64 = DockerImage("ubuntu:22.04", LINUX_ARM64)
    UBUNTU_16_AMD64 = DockerImage("ubuntu:16.04", LINUX_AMD64)
    UBUNTU_16_ARM64 = DockerImage("ubuntu:16.04", LINUX_ARM64)
    CENTOS_7_AMD64 = DockerImage("centos:7", LINUX_AMD64)
    # Currently bugged
    # DockerImage("centos:7", LINUX_ARM64, short_name="centos_7")
    # DockerImage("alpine:3", LINUX_AMD64, short_name="alpine_3"),
    # DockerImage("alpine:3", LINUX_ARM64, short_name="alpine_3"),
    TOMCAT_9_AMD64 = DockerImage("tomcat:9", LINUX_AMD64)
    TOMCAT_9_ARM64 = DockerImage("tomcat:9", LINUX_ARM64)


class JavaRuntimeVersions:
    """ Java runtime versions """

    JAVA_22 = RuntimeVersions("JAVA_22", "22.0.2-zulu")
    JAVA_21 = RuntimeVersions("JAVA_21", "21.0.4-zulu")
    JAVA_17 = RuntimeVersions("JAVA_17", "17.0.12-zulu")
    JAVA_11 = RuntimeVersions("JAVA_17", "11.0.24-zulu")

    @staticmethod
    def get_all_versions():
        return [
            JavaRuntimeVersions.JAVA_22,
            JavaRuntimeVersions.JAVA_21,
            JavaRuntimeVersions.JAVA_17,
            JavaRuntimeVersions.JAVA_11,
        ]


class WeblogDescriptor:
    """ Encapsulates information of the weblog: name, library and supported images with the supported runtime versions """

    def __init__(self, name, library, supported_images) -> None:
        self.name = name
        self.library = library
        self.supported_images = supported_images


# HERE ADD YOUR WEBLOG DEFINITION: SUPPORTED IMAGES AND RUNTIME VERSIONS
DD_LIB_JAVA_INIT_TEST_APP = WeblogDescriptor(
    "dd-lib-java-init-test-app",
    "java",
    [
        SupportedImages.UBUNTU_22_AMD64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        SupportedImages.UBUNTU_22_ARM64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        SupportedImages.UBUNTU_16_AMD64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        SupportedImages.UBUNTU_16_ARM64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        SupportedImages.CENTOS_7_AMD64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
    ],
)

TOMCAT_APP = WeblogDescriptor("tomcat-app", "java", [SupportedImages.TOMCAT_9_AMD64, SupportedImages.TOMCAT_9_ARM64])
JAVA7_APP = WeblogDescriptor("java7-app", "python", [SupportedImages.UBUNTU_22_AMD64])

# HERE ADD YOUR WEBLOG DEFINITION TO THE LIST
ALL_WEBLOGS = [DD_LIB_JAVA_INIT_TEST_APP, TOMCAT_APP, JAVA7_APP]


def _print_matrix(library):
    """ Debug function to print the matrix """
    filtered = [weblog for weblog in ALL_WEBLOGS if weblog.library == library]
    for weblog in filtered:
        print(weblog.name)
        for image in weblog.supported_images:
            print(f"    {image.name()}")
            for version in image.runtime_versions:
                print(f"        {version.version_id}")


def get_github_matrix(library):
    """ Matrix that will be used in the github workflow """
    tests = []
    github_matrix = {"include": []}

    filtered = [weblog for weblog in ALL_WEBLOGS if weblog.library == library]
    for weblog in filtered:
        for image in weblog.supported_images:
            if not image.runtime_versions:
                tests.append({"weblog": weblog.name, "base_image": image.tag, "arch": image.platform, "runtime": ""})
            else:
                for version in image.runtime_versions:
                    tests.append(
                        {
                            "weblog": weblog.name,
                            "base_image": image.tag,
                            "arch": image.platform,
                            "runtime": version.version,
                        }
                    )

    github_matrix["include"] = tests
    return github_matrix


def main():
    _print_matrix("java")
    github_matrix = get_github_matrix("java")
    print(github_matrix)


if __name__ == "__main__":
    main()
