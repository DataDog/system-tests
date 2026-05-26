import argparse
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

parser = argparse.ArgumentParser()
parser.add_argument("--stage", required=True, help="GitLab CI stage for the generated jobs")
parser.add_argument("--library", required=True, default="", help="Library name, used to prefix job names")
parser.add_argument("--params", required=True, help="Path to JSON output from compute-workflow-parameters.py")
parser.add_argument("--ci-image", required=True, help="Full CI image reference for generated jobs")
parser.add_argument("--ref", default="", help="system-tests ref to clone when called from another repository")
parser.add_argument("--push-to-test-optimization", default="false", help="Generate the push_test_optimization job")
parser.add_argument("--test-optimization-datadog-site", default="datadoghq.com", help="Datadog site for Test Optimization")
parser.add_argument("--ssi-library-version", default="", help="DD_INSTALLER_LIBRARY_VERSION for Docker/K8s SSI jobs")
parser.add_argument("--k8s-lib-init-img", default="", help="K8S_LIB_INIT_IMG for libinjection jobs")
parser.add_argument("--ssi-injector-version", default="", help="DD_INSTALLER_INJECTOR_VERSION for dockerssi jobs")
args = parser.parse_args()

with open(args.params) as f:
    params = json.load(f)
scenario_list = params["endtoend"]["scenarios"]
weblog_variants = params["endtoend"]["weblogs"]
binaries_artifact = params["miscs"]["binaries_artifact"]
ci_environment = params["miscs"]["ci_environment"]
parametric = params["parametric"]
dockerssi_scenario_defs = params.get("dockerssi_scenario_defs", {})
libinjection_scenario_defs = params.get("libinjection_scenario_defs", {})

env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent), autoescape=select_autoescape())


def _transform_dockerssi(raw: dict) -> dict:
    """Regroup dockerssi images by arch for easier Jinja2 iteration.

    Input:  {scenario: {weblog: [{image_name: [runtimes], "arch": arch}, ...]}}
    Output: {scenario: {weblog: {arch_short: [{image, runtimes}, ...]}}}
    """
    result: dict = {}
    for scenario, weblogs in raw.items():
        result[scenario] = {}
        for weblog, images in weblogs.items():
            by_arch: dict = {}
            for img in images:
                arch = img["arch"]
                arch_short = arch.replace("linux/", "")
                if arch_short not in by_arch:
                    by_arch[arch_short] = []
                for key, val in img.items():
                    if key != "arch":
                        by_arch[arch_short].append({"image": key, "runtimes": val})
            result[scenario][weblog] = by_arch
    return result


template = env.get_template("system-tests.yml")

print(template.render(
    scenarios=scenario_list,
    stage=args.stage,
    library=args.library,
    weblog_variants=weblog_variants,
    binaries_artifact=binaries_artifact,
    ci_environment=ci_environment,
    parametric=parametric,
    ci_image=args.ci_image,
    ref=args.ref,
    push_to_test_optimization=args.push_to_test_optimization == "true",
    test_optimization_datadog_site=args.test_optimization_datadog_site,
))

if dockerssi_scenario_defs:
    dockerssi_template = env.get_template("dockerssi.yml")
    print(dockerssi_template.render(
        library=args.library,
        ci_environment=ci_environment,
        dockerssi_scenario_defs=_transform_dockerssi(dockerssi_scenario_defs),
        ssi_library_version=args.ssi_library_version,
        ssi_injector_version=args.ssi_injector_version,
    ))

if libinjection_scenario_defs:
    libinjection_template = env.get_template("libinjection.yml")
    print(libinjection_template.render(
        library=args.library,
        ci_environment=ci_environment,
        libinjection_scenario_defs=libinjection_scenario_defs,
        k8s_lib_init_img=args.k8s_lib_init_img,
    ))
