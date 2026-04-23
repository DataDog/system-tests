import argparse
import json
import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
from utils._context._scenarios import _Scenarios
from utils._context._scenarios.core import Scenario

parser = argparse.ArgumentParser()
parser.add_argument("--stage", required=True, help="GitLab CI stage for the generated jobs")
parser.add_argument("--library", default="", help="Library name, used to prefix job names")
parser.add_argument("--params", help="Path to JSON output from compute-workflow-parameters.py")
args = parser.parse_args()

if args.params:
    with open(args.params) as f:
        params = json.load(f)
    scenario_list = params["endtoend"]["scenarios"]
    weblog_variants = params["endtoend"]["weblogs"]
else:
    scenario_list = sorted(var.name for var in vars(_Scenarios).values() if isinstance(var, Scenario))

    python_weblog_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../utils/build/docker/python")
    weblog_variants = sorted(
        f[: -len(".Dockerfile")]
        for f in os.listdir(python_weblog_dir)
        if f.endswith(".Dockerfile") and not f.endswith(".base.Dockerfile")
    )

env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), autoescape=select_autoescape())

template = env.get_template("system-tests.yml")

print(template.render(scenarios=scenario_list, stage=args.stage, library=args.library, weblog_variants=weblog_variants))
