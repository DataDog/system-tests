from __future__ import annotations

try:
    from _internal import ConstGroups, ConstGroup
except ModuleNotFoundError:
    from ._internal import ConstGroups, ConstGroup


class ComponentGroups(ConstGroups):
    # There is an "all" group containing all the items by default
    buildable = ConstGroup()
    """All libraries that support end to end testing (valid arguments for ./build.sh)"""
    easy_win = ConstGroup()
    """All components for which easy win auto activation is enabled"""
    ssi = ConstGroup()
    """SSI components"""
    lib_injection = ConstGroup()
    """K8s Single Step Instrumentation (formerly Lib injection) components"""
    parametric = ConstGroup()
    """Libraries supporting the parametric scenario"""
    otel = ConstGroup()
    """OpenTelemetry libraries, supporting the OTEL_INTEGRATIONS scenario"""
    lambda_lib = ConstGroup()
    """Lambda libraries, supporting all scenarios created from `LambdaScenario` class"""

    def _items(self) -> dict[str, list[ConstGroup]]:
        return {
            "cpp": [self.easy_win, self.lib_injection, self.parametric],
            "cpp_httpd": [self.buildable, self.easy_win],
            "cpp_nginx": [self.buildable, self.easy_win],
            "cpp_kong": [self.buildable, self.easy_win],
            "dotnet": [self.buildable, self.easy_win, self.ssi, self.lib_injection, self.parametric],
            "envoy": [],
            "golang": [self.buildable, self.easy_win, self.lib_injection, self.parametric],
            "haproxy": [],
            "java": [self.buildable, self.easy_win, self.ssi, self.lib_injection, self.parametric],
            "java_lambda": [self.buildable, self.lambda_lib, self.parametric],
            "java_otel": [self.buildable, self.lib_injection, self.otel],
            "nodejs": [self.buildable, self.easy_win, self.ssi, self.lib_injection, self.parametric],
            "nodejs_otel": [self.buildable, self.lib_injection, self.otel],
            "otel_collector": [],
            "php": [self.buildable, self.easy_win, self.ssi, self.lib_injection, self.parametric],
            "python": [self.buildable, self.easy_win, self.ssi, self.lib_injection, self.parametric],
            "python_lambda": [self.buildable, self.easy_win, self.lambda_lib],
            "python_otel": [self.buildable, self.lib_injection, self.otel],
            "ruby": [self.buildable, self.easy_win, self.ssi, self.lib_injection, self.parametric],
            "rust": [self.buildable, self.easy_win, self.lib_injection, self.parametric],
        }


COMPONENT_GROUPS = ComponentGroups()

__all__ = ["COMPONENT_GROUPS"]
