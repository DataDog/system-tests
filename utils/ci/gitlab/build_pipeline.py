import argparse
import json
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
parser.add_argument("--skip-header", action="store_true", help="Skip the workflow/include/variables header (for concatenation)")

args = parser.parse_args()

with open(args.params) as f:
    params = json.load(f)
scenario_list = params["endtoend"]["scenarios"]
weblog_variants = params["endtoend"]["weblogs"]
binaries_artifact = params["miscs"]["binaries_artifact"]
ci_environment = params["miscs"]["ci_environment"]
parametric = params["parametric"]
env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent), autoescape=select_autoescape())


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
    skip_header=args.skip_header,
), end="")
