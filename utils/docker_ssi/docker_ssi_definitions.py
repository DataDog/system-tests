LINUX_AMD64 = "linux/amd64"
LINUX_ARM64 = "linux/arm64"

try:
    from utils.docker_ssi.docker_ssi_model import DockerImage, RuntimeVersions, WeblogDescriptor
except ImportError:
    from docker_ssi_model import DockerImage, RuntimeVersions, WeblogDescriptor


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
