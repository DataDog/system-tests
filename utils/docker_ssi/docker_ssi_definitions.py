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
        self.ORACLELINUX_9_ARM64 = DockerImage("oraclelinux:9", LINUX_ARM64)
        self.ORACLELINUX_9_AMD64 = DockerImage("oraclelinux:9", LINUX_AMD64)
        self.ORACLELINUX_8_ARM64 = DockerImage("oraclelinux:8.10", LINUX_ARM64)
        self.ORACLELINUX_8_AMD64 = DockerImage("oraclelinux:8.10", LINUX_AMD64)

        self.ALMALINUX_9_ARM64 = DockerImage("almalinux:9.4", LINUX_ARM64)
        self.ALMALINUX_9_AMD64 = DockerImage("almalinux:9.4", LINUX_AMD64)
        self.ALMALINUX_8_ARM64 = DockerImage("almalinux:8.10", LINUX_ARM64)
        self.ALMALINUX_8_AMD64 = DockerImage("almalinux:8.10", LINUX_AMD64)

        # Currently bugged
        # DockerImage("centos:7", LINUX_ARM64, short_name="centos_7")
        # DockerImage("alpine:3", LINUX_AMD64, short_name="alpine_3"),
        # DockerImage("alpine:3", LINUX_ARM64, short_name="alpine_3"),
        self.TOMCAT_9_AMD64 = DockerImage("tomcat:9", LINUX_AMD64)
        self.TOMCAT_9_ARM64 = DockerImage("tomcat:9", LINUX_ARM64)
        self.WEBSPHERE_AMD64 = DockerImage("icr.io/appcafe/websphere-traditional", LINUX_AMD64)
        self.JBOSS_AMD64 = DockerImage("quay.io/wildfly/wildfly:26.1.2.Final", LINUX_AMD64)


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


class PHPRuntimeInstallableVersions:
    """ PHP runtime versions that can be installed automatically"""

    PHP74 = RuntimeInstallableVersion("PHP74", "7.4")
    PHP83 = RuntimeInstallableVersion("PHP83", "8.3")

    @staticmethod
    def get_all_versions():
        return [
            PHPRuntimeInstallableVersions.PHP74,
            PHPRuntimeInstallableVersions.PHP83,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in PHPRuntimeInstallableVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f"PHP version {version} not supported")


class PythonRuntimeInstallableVersions:
    """ Python runtime versions that can be installed automatically"""

    PY37 = RuntimeInstallableVersion("PY37", "3.7.16")
    PY38 = RuntimeInstallableVersion("PY38", "3.8.20")
    PY39 = RuntimeInstallableVersion("PY39", "3.9.20")
    PY310 = RuntimeInstallableVersion("PY310", "3.10.15")
    PY311 = RuntimeInstallableVersion("PY311", "3.11.10")
    PY312 = RuntimeInstallableVersion("PY312", "3.12.7")

    @staticmethod
    def get_all_versions():
        return [
            PythonRuntimeInstallableVersions.PY37,
            PythonRuntimeInstallableVersions.PY38,
            PythonRuntimeInstallableVersions.PY39,
            PythonRuntimeInstallableVersions.PY310,
            PythonRuntimeInstallableVersions.PY311,
            PythonRuntimeInstallableVersions.PY312,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in PythonRuntimeInstallableVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f"Python version {version} not supported")


class RubyRuntimeInstallableVersions:
    """ Ruby runtime versions that can be installed automatically"""

    RB27 = RuntimeInstallableVersion("RB27", "2.7")
    RB30 = RuntimeInstallableVersion("RB30", "3.0")
    RB31 = RuntimeInstallableVersion("RB31", "3.1")
    RB32 = RuntimeInstallableVersion("RB32", "3.2.6")

    @staticmethod
    def get_all_versions():
        return [
            RubyRuntimeInstallableVersions.RB27,
            RubyRuntimeInstallableVersions.RB30,
            RubyRuntimeInstallableVersions.RB31,
            RubyRuntimeInstallableVersions.RB32,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in RubyRuntimeInstallableVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f"Ruby version {version} not supported")


# HERE ADD YOUR WEBLOG DEFINITION: SUPPORTED IMAGES AND INSTALABLE RUNTIME VERSIONS
# Maybe a weblog app contains preinstalled language runtime, in this case we define the weblog without runtime version
JETTY_APP = WeblogDescriptor(
    "jetty-app",
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
        SupportedImages().ORACLELINUX_9_AMD64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().ORACLELINUX_9_ARM64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().ORACLELINUX_8_AMD64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().ORACLELINUX_8_ARM64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().ALMALINUX_9_AMD64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().ALMALINUX_9_ARM64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().ALMALINUX_8_AMD64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().ALMALINUX_8_ARM64.with_allowed_runtime_versions(
            JavaRuntimeInstallableVersions.get_all_versions()
        ),
        # Commented due to APMON-1491
        # SupportedImages().CENTOS_7_AMD64.with_allowed_runtime_versions(
        #    JavaRuntimeInstallableVersions.get_all_versions()
        # ),
    ],
)


TOMCAT_APP = WeblogDescriptor("tomcat-app", "java", [SupportedImages().TOMCAT_9_ARM64])
JAVA7_APP = WeblogDescriptor("java7-app", "java", [SupportedImages().UBUNTU_22_ARM64])
WEBSPHERE_APP = WeblogDescriptor("websphere-app", "java", [SupportedImages().WEBSPHERE_AMD64])
JBOSS_APP = WeblogDescriptor("jboss-app", "java", [SupportedImages().JBOSS_AMD64])

PHP_APP = WeblogDescriptor(
    "php-app",
    "php",
    [SupportedImages().UBUNTU_22_AMD64.with_allowed_runtime_versions(PHPRuntimeInstallableVersions.get_all_versions())],
)

PY_APP = WeblogDescriptor(
    "py-app",
    "python",
    [
        SupportedImages().UBUNTU_22_ARM64.with_allowed_runtime_versions(
            PythonRuntimeInstallableVersions.get_all_versions()
        )
    ],
)

RB_APP = WeblogDescriptor(
    "rb-app",
    "ruby",
    [
        SupportedImages().UBUNTU_22_ARM64.with_allowed_runtime_versions(
            RubyRuntimeInstallableVersions.get_all_versions()
        )
    ],
)

# HERE ADD YOUR WEBLOG DEFINITION TO THE LIST
ALL_WEBLOGS = [JETTY_APP, TOMCAT_APP, JAVA7_APP, WEBSPHERE_APP, JBOSS_APP, PHP_APP, PY_APP, RB_APP]
