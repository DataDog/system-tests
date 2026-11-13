"""Check that docs/understand/weblogs/parametric_weblog.md documents every endpoint called by the parametric client."""

import ast
from pathlib import Path

from utils import scenarios

CLIENT = Path("utils/docker_fixtures/_test_clients/_test_client_parametric.py")
DOC = Path("docs/understand/weblogs/parametric_weblog.md")
HTTP_METHODS = {"get", "post", "put", "delete"}


def _string_constants(node: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _client_endpoints() -> set[tuple[str, str]]:
    """Return the (HTTP method, path) of every request sent with `self._session.<method>(self._url(...))`"""
    endpoints: set[tuple[str, str]] = set()
    for function in ast.walk(ast.parse(CLIENT.read_text())):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # paths assigned to a variable, then passed to self._url(variable)
        assigned: dict[str, list[str]] = {}
        for node in ast.walk(function):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned.setdefault(target.id, []).extend(_string_constants(node.value))

        for call in ast.walk(function):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
                continue
            if call.func.attr not in HTTP_METHODS:
                continue
            for arg in call.args:
                if not (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "_url"):
                    continue
                path_arg = arg.args[0]
                paths: list[str]
                if isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
                    paths = [path_arg.value]
                elif isinstance(path_arg, ast.Name):
                    paths = assigned.get(path_arg.id, [])
                else:
                    paths = _string_constants(path_arg)
                endpoints.update((call.func.attr.upper(), path) for path in paths if path.startswith("/"))

    return endpoints


@scenarios.test_the_test
def test_client_endpoints_are_found() -> None:
    endpoints = _client_endpoints()
    assert ("POST", "/trace/span/start") in endpoints
    assert ("GET", "/otel/effective_config") in endpoints  # path held in a variable


@scenarios.test_the_test
def test_every_client_endpoint_is_documented() -> None:
    doc = DOC.read_text()
    missing = sorted(f"{method} {path}" for method, path in _client_endpoints() if f"#### `{method} {path}`" not in doc)
    assert not missing, f"Endpoints called by {CLIENT} but not documented in {DOC}: {missing}"
