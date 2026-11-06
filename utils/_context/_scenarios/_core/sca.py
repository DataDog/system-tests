from utils._context.containers import TestedContainer


def configure_sca_advisories(container: TestedContainer) -> None:
    library = container.image.labels["system-tests-library"]
    if library not in ("java", "python", "java_lambda", "python_lambda"):
        return

    catalog_path = "/sca/advisories.json"
    language = library.removesuffix("_lambda")
    container.volumes[f"./tests/appsec/sca/{language}/advisories.json"] = {"bind": catalog_path, "mode": "ro"}
    container.environment["_DD_APPSEC_SCA_CVE_FILE"] = catalog_path
