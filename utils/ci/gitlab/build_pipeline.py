import argparse
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

parser = argparse.ArgumentParser()
parser.add_argument("--stage", required=True, help="GitLab CI stage for the generated jobs")
parser.add_argument("--library", required=True, default="", help="Library name, used to prefix job names")
parser.add_argument("--params", required=True, help="Path to JSON output from compute-workflow-parameters.py")
args = parser.parse_args()

with open(args.params) as f:
    params = json.load(f)
scenario_list = params["endtoend"]["scenarios"]
weblog_variants = params["endtoend"]["weblogs"]
binaries_artifact = params["miscs"]["binaries_artifact"]

env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent), autoescape=select_autoescape())

template = env.get_template("system-tests.yml")

print(template.render(scenarios=scenario_list, stage=args.stage, library=args.library, weblog_variants=weblog_variants, binaries_artifact=binaries_artifact))
