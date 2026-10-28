import ast
from pathlib import Path

from utils import scenarios
from utils._context._scenarios import get_all_scenarios

SCENARIOS_INIT = Path(__file__).parents[2] / "utils" / "_context" / "_scenarios" / "__init__.py"
SCENARIOS_PACKAGE = "utils._context._scenarios"


@scenarios.test_the_test
def test_scenarios_class_sets_no_value():
    """_Scenarios only instantiates scenarios: their configuration lives in their definition module, so that modifying a
    scenario only runs this scenario in CI (see libraries_and_scenarios_rules.yml).
    """
    tree = ast.parse(SCENARIOS_INIT.read_text())
    scenarios_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_Scenarios")

    for statement in scenarios_class.body:
        assert isinstance(statement, ast.Assign), f"line {statement.lineno}: only `name = Class()` is allowed"
        call = statement.value
        assert isinstance(call, ast.Call), f"line {statement.lineno}: only `name = Class()` is allowed"
        assert isinstance(call.func, ast.Name), f"line {statement.lineno}: only `name = Class()` is allowed"
        assert not call.args, f"line {statement.lineno}: move the arguments of {call.func.id} to its class"
        assert not call.keywords, f"line {statement.lineno}: move the arguments of {call.func.id} to its class"


@scenarios.test_the_test
def test_every_scenario_is_defined_in_a_definition_module():
    """A scenario is defined by its own class, in a module of utils/_context/_scenarios/ (not in _core/): when such a
    module is modified, CI runs the scenarios it defines (see compute_libraries_and_scenarios.py).
    """
    misplaced = {
        scenario.name: type(scenario).__module__
        for scenario in get_all_scenarios()
        if type(scenario).__module__.count(".") != SCENARIOS_PACKAGE.count(".") + 1
        or not type(scenario).__module__.startswith(f"{SCENARIOS_PACKAGE}.")
        or type(scenario).__module__.startswith(f"{SCENARIOS_PACKAGE}._core")
    }
    assert not misplaced, f"Scenarios defined outside a definition module of {SCENARIOS_PACKAGE}: {misplaced}"


@scenarios.test_the_test
def test_definition_modules_only_import_core():
    """Definition modules only import base classes from ._core: never another definition module, nor the package."""
    errors = []
    for path in sorted(SCENARIOS_INIT.parent.glob("*.py")):
        if path.name == "__init__.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 1 and module.split(".")[0] != "_core":
                    errors.append(f"{path.name}:{node.lineno}: from .{module} import ...")
                elif node.level > 1:
                    errors.append(f"{path.name}:{node.lineno}: relative import of a parent package")
                elif node.level == 0 and module.startswith(SCENARIOS_PACKAGE):
                    errors.append(f"{path.name}:{node.lineno}: from {module} import ... (use from ._core import ...)")
            elif isinstance(node, ast.Import):
                errors += [
                    f"{path.name}:{node.lineno}: import {alias.name}"
                    for alias in node.names
                    if alias.name.startswith(SCENARIOS_PACKAGE)
                ]
    assert not errors, "\n".join(errors)
