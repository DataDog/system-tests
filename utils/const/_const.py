from pathlib import Path
from ._internal import Const


class Libraries(Const):
    """List of libraries"""

    _path = Path("utils/const/libraries.yml")

    def _build_attributes(self) -> None:
        self.all = self.groups["all"]
        self.buildable = self.groups["buildable"]
        self.easy_win = self.groups["easy_win"]
        self.gitlab = self.groups["gitlab"]
        self.lib_injection = self.groups["lib_injection"]
        self.parametric = self.groups["parametric"]
        self.otel = self.groups["otel"]
        self.lambda_lib = self.groups["lambda_lib"]


# Required to avoid type checking errors
LIBRARIES = Libraries()

__all__ = ["LIBRARIES"]
