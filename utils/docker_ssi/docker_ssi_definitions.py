LINUX_AMD64 = "linux/amd64"
LINUX_ARM64 = "linux/arm64"

try:
    from utils.docker_ssi.docker_ssi_model import DockerImage, RuntimeInstallableVersion, WeblogDescriptor
except ImportError:
    from docker_ssi_model import DockerImage, RuntimeInstallableVersion, WeblogDescriptor


class SupportedImages:
    """ All supported images """

    def __init__(self) -> None:
        # Try to set the same name as utils/_context/virtual_machines.py
        self.UBUNTU_22_AMD64 = DockerImage("Ubuntu_22", "ubuntu:22.04", LINUX_AMD64)
        self.UBUNTU_22_ARM64 = DockerImage("Ubuntu_22", "ubuntu:22.04", LINUX_ARM64)
        self.UBUNTU_16_AMD64 = DockerImage("Ubuntu_16", "ubuntu:16.04", LINUX_AMD64)
        self.UBUNTU_16_ARM64 = DockerImage("Ubuntu_16", "ubuntu:16.04", LINUX_ARM64)
        self.CENTOS_7_AMD64 = DockerImage("CentOS_7", "centos:7", LINUX_AMD64)
        self.ORACLELINUX_9_ARM64 = DockerImage("OracleLinux_9", "oraclelinux:9", LINUX_ARM64)
        self.ORACLELINUX_9_AMD64 = DockerImage("OracleLinux_9", "oraclelinux:9", LINUX_AMD64)
        self.ORACLELINUX_8_ARM64 = DockerImage("OracleLinux_8_10", "oraclelinux:8.10", LINUX_ARM64)
        self.ORACLELINUX_8_AMD64 = DockerImage("OracleLinux_8_10", "oraclelinux:8.10", LINUX_AMD64)

        self.ALMALINUX_9_ARM64 = DockerImage("AlmaLinux_9", "almalinux:9.4", LINUX_ARM64)
        self.ALMALINUX_9_AMD64 = DockerImage("AlmaLinux_9", "almalinux:9.4", LINUX_AMD64)
        self.ALMALINUX_8_ARM64 = DockerImage("AlmaLinux_8", "almalinux:8.10", LINUX_ARM64)
        self.ALMALINUX_8_AMD64 = DockerImage("AlmaLinux_8", "almalinux:8.10", LINUX_AMD64)

        # Currently bugged
        # DockerImage("centos:7", LINUX_ARM64, short_name="centos_7")
        # DockerImage("alpine:3", LINUX_AMD64, short_name="alpine_3"),
        # DockerImage("alpine:3", LINUX_ARM64, short_name="alpine_3"),
        self.TOMCAT_9_AMD64 = DockerImage("Tomcat_9", "tomcat:9", LINUX_AMD64)
        self.TOMCAT_9_ARM64 = DockerImage("Tomcat_9", "tomcat:9", LINUX_ARM64)
        self.WEBSPHERE_AMD64 = DockerImage("Websphere", "icr.io/appcafe/websphere-traditional", LINUX_AMD64)
        self.JBOSS_AMD64 = DockerImage("Wildfly", "quay.io/wildfly/wildfly:26.1.2.Final", LINUX_AMD64)

    def get_internal_name_from_base_image(self, base_image, arch):
        for image in self.__dict__.values():
            if image.tag == base_image and image.platform == arch:
                return image.internal_name
        raise ValueError(f"Image {base_image} not supported")


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

    PHP56 = RuntimeInstallableVersion("PHP56", "5.6")  # Not supported (EOL runtime)
    PHP70 = RuntimeInstallableVersion("PHP70", "7.0")
    PHP71 = RuntimeInstallableVersion("PHP71", "7.1")
    PHP72 = RuntimeInstallableVersion("PHP72", "7.2")
    PHP73 = RuntimeInstallableVersion("PHP73", "7.3")
    PHP74 = RuntimeInstallableVersion("PHP74", "7.4")
    PHP80 = RuntimeInstallableVersion("PHP80", "8.0")
    PHP81 = RuntimeInstallableVersion("PHP81", "8.1")
    PHP82 = RuntimeInstallableVersion("PHP82", "8.2")
    PHP83 = RuntimeInstallableVersion("PHP83", "8.3")

    @staticmethod
    def get_all_versions():
        return [
            PHPRuntimeInstallableVersions.PHP56,
            PHPRuntimeInstallableVersions.PHP70,
            PHPRuntimeInstallableVersions.PHP71,
            PHPRuntimeInstallableVersions.PHP72,
            PHPRuntimeInstallableVersions.PHP73,
            PHPRuntimeInstallableVersions.PHP74,
            PHPRuntimeInstallableVersions.PHP80,
            PHPRuntimeInstallableVersions.PHP81,
            PHPRuntimeInstallableVersions.PHP82,
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

    PY36 = RuntimeInstallableVersion("PY36", "3.6.15")  # Not supported (EOL runtime)
    PY37 = RuntimeInstallableVersion("PY37", "3.7.16")
    PY38 = RuntimeInstallableVersion("PY38", "3.8.20")
    PY39 = RuntimeInstallableVersion("PY39", "3.9.20")
    PY310 = RuntimeInstallableVersion("PY310", "3.10.15")
    PY311 = RuntimeInstallableVersion("PY311", "3.11.10")
    PY312 = RuntimeInstallableVersion("PY312", "3.12.7")

    @staticmethod
    def get_all_versions():
        return [
            PythonRuntimeInstallableVersions.PY36,
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


class JSRuntimeInstallableVersions:
    """Node.js runtime versions that can be installed automatically"""

    JS12 = RuntimeInstallableVersion("JS12", "12.22.12")
    JS14 = RuntimeInstallableVersion("JS14", "14.21.3")
    JS16 = RuntimeInstallableVersion("JS16", "16.20.2")
    JS18 = RuntimeInstallableVersion("JS18", "18.20.5")
    JS20 = RuntimeInstallableVersion("JS20", "20.18.1")
    JS22 = RuntimeInstallableVersion("JS22", "22.11.0")

    @staticmethod
    def get_all_versions():
        return [
            JSRuntimeInstallableVersions.JS12,
            JSRuntimeInstallableVersions.JS14,
            JSRuntimeInstallableVersions.JS18,
            JSRuntimeInstallableVersions.JS18,
            JSRuntimeInstallableVersions.JS20,
            JSRuntimeInstallableVersions.JS22,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in JSRuntimeInstallableVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f"Node.js version {version} not supported")


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
    [
        SupportedImages().UBUNTU_22_AMD64.with_allowed_runtime_versions(
            PHPRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().UBUNTU_22_ARM64.with_allowed_runtime_versions(
            PHPRuntimeInstallableVersions.get_all_versions()
        ),
    ],
)

PY_APP = WeblogDescriptor(
    "py-app",
    "python",
    [
        SupportedImages().UBUNTU_22_ARM64.with_allowed_runtime_versions(
            PythonRuntimeInstallableVersions.get_all_versions()
        ),
    ],
)

JS_APP = WeblogDescriptor(
    "js-app",
    "nodejs",
    [
        SupportedImages().UBUNTU_22_AMD64.with_allowed_runtime_versions(
            JSRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().UBUNTU_22_ARM64.with_allowed_runtime_versions(
            JSRuntimeInstallableVersions.get_all_versions()
        ),
    ],
)

# HERE ADD YOUR WEBLOG DEFINITION TO THE LIST
ALL_WEBLOGS = [
    JETTY_APP,
    TOMCAT_APP,
    JAVA7_APP,
    WEBSPHERE_APP,
    JBOSS_APP,
    PHP_APP,
    PY_APP,
    JS_APP,
]
