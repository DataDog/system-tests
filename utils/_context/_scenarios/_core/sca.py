from utils._context.containers import TestedContainer


def configure_sca_advisories(container: TestedContainer) -> None:
    library = container.image.labels["system-tests-library"]
    language = library.removesuffix("_lambda")

    if language == "python":
        if library == "python_lambda":
            package_root = "/opt/python/lib/python3.13/site-packages"
        elif any(volume["bind"] == "/volumes/dd-trace-py" for volume in container.volumes.values()):
            package_root = "/volumes/dd-trace-py"
        else:
            assert container.image.env is not None
            python_version = ".".join(container.image.env["PYTHON_VERSION"].split(".")[:2])
            package_root = f"/usr/local/lib/python{python_version}/site-packages"
        catalog_path = f"{package_root}/ddtrace/appsec/sca/_cve_data.json"
    elif language == "java":
        catalog_path = "/sca/sca_cves.json"
        # The agent checks bootstrap resources before its bundled classpath resources.
        java_options = (
            container.environment.get("JAVA_TOOL_OPTIONS", (container.image.env or {}).get("JAVA_TOOL_OPTIONS", ""))
            or ""
        )
        container.environment["JAVA_TOOL_OPTIONS"] = f"{java_options} -Xbootclasspath/a:/sca".strip()
    else:
        return

    container.volumes[f"./tests/appsec/sca/{language}/advisories.json"] = {"bind": catalog_path, "mode": "ro"}
