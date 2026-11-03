from utils._context.containers import TestedContainer


def configure_sca_advisories(container: TestedContainer) -> None:
    library = container.image.labels["system-tests-library"]
    match library:
        case "python_lambda":
            catalog_path = "/opt/python/lib/python3.13/site-packages/ddtrace/appsec/sca/_cve_data.json"
        case "python" if any(volume["bind"] == "/volumes/dd-trace-py" for volume in container.volumes.values()):
            catalog_path = "/volumes/dd-trace-py/ddtrace/appsec/sca/_cve_data.json"
        case "python":
            assert container.image.env is not None
            python_version = ".".join(container.image.env["PYTHON_VERSION"].split(".")[:2])
            catalog_path = f"/usr/local/lib/python{python_version}/site-packages/ddtrace/appsec/sca/_cve_data.json"
        case "java" | "java_lambda":
            catalog_path = "/sca/sca_cves.json"
            # The agent checks bootstrap resources before its bundled classpath resources.
            java_options = (
                container.environment.get("JAVA_TOOL_OPTIONS", (container.image.env or {}).get("JAVA_TOOL_OPTIONS", ""))
                or ""
            )
            container.environment["JAVA_TOOL_OPTIONS"] = f"{java_options} -Xbootclasspath/a:/sca".strip()
        case _:
            return

    language = library.removesuffix("_lambda")
    container.volumes[f"./tests/appsec/sca/{language}/advisories.json"] = {"bind": catalog_path, "mode": "ro"}
