LINUX_AMD64 = "linux/amd64"
LINUX_ARM64 = "linux/arm64"

try:
    from utils.docker_ssi.docker_ssi_model import RuntimeInstallableVersion
except ImportError:
    from docker_ssi_model import RuntimeInstallableVersion


class JavaRuntimeInstallableVersions:
    """Java runtime versions that can be installed automatically"""

    JAVA_24 = RuntimeInstallableVersion("JAVA_24", "24.0.1-zulu")
    JAVA_21 = RuntimeInstallableVersion("JAVA_21", "21.0.7-zulu")
    JAVA_17 = RuntimeInstallableVersion("JAVA_17", "17.0.15-zulu")
    JAVA_11 = RuntimeInstallableVersion("JAVA_11", "11.0.27-zulu")

    @staticmethod
    def get_all_versions():
        return [
            JavaRuntimeInstallableVersions.JAVA_24,
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
    """PHP runtime versions that can be installed automatically"""

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
    """Python runtime versions that can be installed automatically"""

    PY36 = RuntimeInstallableVersion("PY36", "3.6.15")  # Not supported (EOL runtime)
    PY310 = RuntimeInstallableVersion("PY310", "3.10.15")
    PY39 = RuntimeInstallableVersion("PY39", "3.9.20")
    PY311 = RuntimeInstallableVersion("PY311", "3.11.10")
    PY312 = RuntimeInstallableVersion("PY312", "3.12.7")
    PY313 = RuntimeInstallableVersion("PY312", "3.13.8")
    PY314 = RuntimeInstallableVersion("PY312", "3.14.0")

    @staticmethod
    def get_all_versions():
        return [
            PythonRuntimeInstallableVersions.PY36,
            PythonRuntimeInstallableVersions.PY39,
            PythonRuntimeInstallableVersions.PY310,
            PythonRuntimeInstallableVersions.PY311,
            PythonRuntimeInstallableVersions.PY312,
            PythonRuntimeInstallableVersions.PY313,
            PythonRuntimeInstallableVersions.PY314,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in PythonRuntimeInstallableVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f"Python version {version} not supported")


class JSRuntimeInstallableVersions:
    """Node.js runtime versions that can be installed automatically"""

    JS1200 = RuntimeInstallableVersion("JS1200", "12.0")
    JS1222 = RuntimeInstallableVersion("JS1222", "12.22")
    JS1400 = RuntimeInstallableVersion("JS1400", "14.0")
    JS1421 = RuntimeInstallableVersion("JS1421", "14.21")
    JS1600 = RuntimeInstallableVersion("JS1600", "16.0")
    JS1620 = RuntimeInstallableVersion("JS1620", "16.20")
    JS1800 = RuntimeInstallableVersion("JS1800", "18.0")
    JS1820 = RuntimeInstallableVersion("JS1820", "18.20")
    JS2000 = RuntimeInstallableVersion("JS2000", "20.0")
    JS2018 = RuntimeInstallableVersion("JS2018", "20.18")
    JS2200 = RuntimeInstallableVersion("JS2200", "22.0")
    JS2211 = RuntimeInstallableVersion("JS2211", "22.11")
    JS2300 = RuntimeInstallableVersion("JS2300", "23.0")
    JS2303 = RuntimeInstallableVersion("JS2303", "23.3")

    @staticmethod
    def get_all_versions():
        return [
            JSRuntimeInstallableVersions.JS1200,
            JSRuntimeInstallableVersions.JS1222,
            JSRuntimeInstallableVersions.JS1400,
            JSRuntimeInstallableVersions.JS1421,
            JSRuntimeInstallableVersions.JS1600,
            JSRuntimeInstallableVersions.JS1620,
            JSRuntimeInstallableVersions.JS1800,
            JSRuntimeInstallableVersions.JS1820,
            JSRuntimeInstallableVersions.JS2000,
            JSRuntimeInstallableVersions.JS2018,
            JSRuntimeInstallableVersions.JS2200,
            JSRuntimeInstallableVersions.JS2211,
            JSRuntimeInstallableVersions.JS2300,
            JSRuntimeInstallableVersions.JS2303,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in JSRuntimeInstallableVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f"Node.js version {version} not supported")


class DotnetRuntimeInstallableVersions:
    """.NET runtime versions that can be installed automatically"""

    DOTNET80 = RuntimeInstallableVersion("DOTNET80", "8.0.404")
    DOTNET70 = RuntimeInstallableVersion("DOTNET70", "7.0.410")
    DOTNET60 = RuntimeInstallableVersion("DOTNET60", "6.0.428")

    @staticmethod
    def get_all_versions():
        return [
            DotnetRuntimeInstallableVersions.DOTNET80,
            DotnetRuntimeInstallableVersions.DOTNET70,
            DotnetRuntimeInstallableVersions.DOTNET60,
        ]

    @staticmethod
    def get_version_id(version):
        for version_check in DotnetRuntimeInstallableVersions.get_all_versions():
            if version_check.version == version:
                return version_check.version_id
        raise ValueError(f".NET version {version} not supported")
