import argparse
import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
from utils._context._scenarios import _Scenarios
from utils._context._scenarios.core import Scenario

parser = argparse.ArgumentParser()
parser.add_argument("--stage", required=True, help="GitLab CI stage for the generated jobs")
args = parser.parse_args()

scenario_list = []
for var in vars(_Scenarios).values():
    if not isinstance(var, Scenario):
        continue
    scenario_list.append(var.name)

scenario_list.sort()

python_weblog_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../utils/build/docker/python")
python_variants = sorted(
    f[: -len(".Dockerfile")]
    for f in os.listdir(python_weblog_dir)
    if f.endswith(".Dockerfile") and not f.endswith(".base.Dockerfile")
)

env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), autoescape=select_autoescape())

template = env.get_template("system-tests.yml")

print(template.render(scenarios=scenario_list, stage=args.stage, python_variants=python_variants))
