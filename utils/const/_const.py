from ._internal import ConstGroups, ConstGroup


class ComponentGroups(ConstGroups):
    buildable = ConstGroup()
    easy_win = ConstGroup()
    ssi = ConstGroup()
    lib_injection = ConstGroup()
    parametric = ConstGroup()
    otel = ConstGroup()
    lambda_lib = ConstGroup()

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
