LINUX_AMD64 = "linux/amd64"
LINUX_ARM64 = "linux/arm64"

try:
    from utils.docker_ssi.docker_ssi_model import DockerImage, RuntimeInstallableVersion, WeblogDescriptor
except ImportError:
    from docker_ssi_model import DockerImage, RuntimeInstallableVersion, WeblogDescriptor


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


class JavaRuntimeInstallableVersions:
    """ Java runtime versions that can be installed automatically"""

    JAVA_22 = RuntimeInstallableVersion("JAVA_22", "22.0.2-zulu")
    JAVA_21 = RuntimeInstallableVersion("JAVA_21", "21.0.4-zulu")
    JAVA_17 = RuntimeInstallableVersion("JAVA_17", "17.0.12-zulu")
    JAVA_11 = RuntimeInstallableVersion("JAVA_11", "11.0.24-zulu")

    @staticmethod
    def get_all_versions():
        return [
            JavaRuntimeInstallableVersions.JAVA_22,
            JavaRuntimeInstallableVersions.JAVA_21,
            JavaRuntimeInstallableVersions.JAVA_17,
            JavaRuntimeInstallableVersions.JAVA_11,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in JavaRuntimeInstallableVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f"Java version {version} not supported")


# HERE ADD YOUR WEBLOG DEFINITION: SUPPORTED IMAGES AND INSTALABLE RUNTIME VERSIONS
# Maybe a weblog app contains preinstalled language runtime, in this case we define the weblog without runtime version
JAVA_APP_XX = WeblogDescriptor(
    "java-appXX",
    "java",
    [
        SupportedImages().UBUNTU_22_AMD64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().UBUNTU_22_ARM64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().UBUNTU_16_AMD64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().UBUNTU_16_ARM64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().CENTOS_7_AMD64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
    ],
)


JAVA_APP = WeblogDescriptor(
    "java-app",
    "java",
    [SupportedImages().UBUNTU_22_ARM64.add_allowed_runtime_version(JavaRuntimeInstallableVersions.JAVA_11)],
)

TOMCAT_APP = WeblogDescriptor("tomcat-app", "java", [SupportedImages().TOMCAT_9_ARM64])
JAVA7_APP = WeblogDescriptor("java7-app", "java", [SupportedImages().UBUNTU_22_ARM64])

# HERE ADD YOUR WEBLOG DEFINITION TO THE LIST
ALL_WEBLOGS = [JAVA_APP, TOMCAT_APP, JAVA7_APP]
