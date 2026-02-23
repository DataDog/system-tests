from pathlib import Path
from ._internal import Const, ConstList


class Constants(ConstList):
    class Libraries(Const):
        path = Path("utils/const/libraries.yml")

        def build_attributes(self) -> None:
            self.all = self.categories["all"]
            self.buildable = self.categories["buildable"]
            self.easy_win = self.categories["easy_win"]
            self.gitlab = self.categories["gitlab"]
            self.lib_injection = self.categories["lib_injection"]
            self.parametric = self.categories["parametric"]
            self.otel = self.categories["otel"]
            self.lambda_lib = self.categories["lambda_lib"]


Constants().build_exports(globals())

LIBRARIES: Constants.Libraries
__all__ = ["LIBRARIES"]
