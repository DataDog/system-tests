import os
import json

LINUX_AMD64 = "linux/amd64"
LINUX_ARM64 = "linux/arm64"


class RuntimeVersions:
    """ Encapsulates information of the version of the language """

    def __init__(self, version_id, version) -> None:
        self.version_id = version_id
        self.version = version

    @staticmethod
    def getVersion_id(library, version):
        if library == "java":
            return JavaRuntimeVersions.get_version_id(version)
        else:
            raise ValueError(f"Library {library} not supported")


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


class SupportedImages:
    """ All supported images """

    def __init__(self) -> None:

        self.UBUNTU_22_AMD64 = DockerImage("ubuntu:22.04", LINUX_AMD64)
        self.UBUNTU_22_ARM64 = DockerImage("ubuntu:22.04", LINUX_ARM64)
        self.UBUNTU_16_AMD64 = DockerImage("ubuntu:16.04", LINUX_AMD64)
        self.UBUNTU_16_ARM64 = DockerImage("ubuntu:16.04", LINUX_ARM64)
        self.CENTOS_7_AMD64 = DockerImage("centos:7", LINUX_AMD64)
        # Currently bugged
        # DockerImage("centos:7", LINUX_ARM64, short_name="centos_7")
        # DockerImage("alpine:3", LINUX_AMD64, short_name="alpine_3"),
        # DockerImage("alpine:3", LINUX_ARM64, short_name="alpine_3"),
        self.TOMCAT_9_AMD64 = DockerImage("tomcat:9", LINUX_AMD64)
        self.TOMCAT_9_ARM64 = DockerImage("tomcat:9", LINUX_ARM64)


class JavaRuntimeVersions:
    """ Java runtime versions """

    JAVA_22 = RuntimeVersions("JAVA_22", "22.0.2-zulu")
    JAVA_21 = RuntimeVersions("JAVA_21", "21.0.4-zulu")
    JAVA_17 = RuntimeVersions("JAVA_17", "17.0.12-zulu")
    JAVA_11 = RuntimeVersions("JAVA_11", "11.0.24-zulu")

    @staticmethod
    def get_all_versions():
        return [
            JavaRuntimeVersions.JAVA_22,
            JavaRuntimeVersions.JAVA_21,
            JavaRuntimeVersions.JAVA_17,
            JavaRuntimeVersions.JAVA_11,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in JavaRuntimeVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f"Java version {version} not supported")


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
                            "unique_name": f"{self.name}_{image.tag.replace(':','_').replace('.','_')}_{image.platform.replace('/','_')}_{runtime_version.version_id}",
                        }
                    )
        return matrix_combinations


# HERE ADD YOUR WEBLOG DEFINITION: SUPPORTED IMAGES AND RUNTIME VERSIONS
DD_LIB_JAVA_INIT_TEST_APP_2 = WeblogDescriptor(
    "dd-lib-java-init-test-app",
    "java",
    [
        SupportedImages().UBUNTU_22_AMD64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        SupportedImages().UBUNTU_22_ARM64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        SupportedImages().UBUNTU_16_AMD64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        SupportedImages().UBUNTU_16_ARM64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        SupportedImages().CENTOS_7_AMD64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
    ],
)

# HERE ADD YOUR WEBLOG DEFINITION: SUPPORTED IMAGES AND RUNTIME VERSIONS
DD_LIB_JAVA_INIT_TEST_APP = WeblogDescriptor(
    "dd-lib-java-init-test-app",
    "java",
    [
        SupportedImages().UBUNTU_22_ARM64.add_allowed_runtime_version(JavaRuntimeVersions.JAVA_11)
        #  SupportedImages.UBUNTU_22_ARM64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        #  SupportedImages.UBUNTU_16_AMD64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        #  SupportedImages.UBUNTU_16_ARM64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
        #  SupportedImages.CENTOS_7_AMD64.with_allowed_runtime_versions(JavaRuntimeVersions.get_all_versions()),
    ],
)

TOMCAT_APP = WeblogDescriptor(
    "tomcat-app", "python", [SupportedImages().TOMCAT_9_AMD64, SupportedImages().TOMCAT_9_ARM64]
)
JAVA7_APP = WeblogDescriptor("java7-app", "python", [SupportedImages().UBUNTU_22_AMD64])

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
        weblog_matrix = weblog.get_matrix()
        if not weblog_matrix:
            continue
        tests = tests + weblog_matrix

    github_matrix["include"] = tests
    return github_matrix


def main():
    if not os.getenv("TEST_LIBRARY"):
        raise ValueError("TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby")
    github_matrix = get_github_matrix(os.getenv("TEST_LIBRARY"))
    print(json.dumps(github_matrix))


if __name__ == "__main__":
    main()
