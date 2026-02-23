from functools import reduce
from pathlib import Path
from typing import Any

import yaml


def load(path: Path) -> dict[str, set[str]]:
    content = yaml.safe_load(path.read_text())
    categories: dict[str, set[str]] = {"all": set()}
    for element, element_cats in content.items():
        categories["all"].add(element)
        for category in element_cats:
            if category not in categories:
                categories[category] = set()
            categories[category].add(element)
    return categories


class Const:
    categories: dict[str, set[str]]
    path: Path

    def __init__(self) -> None:
        self.categories = load(self.path)
        self.build_attributes()

    def shell_export(self, name: str) -> str:
        return reduce(lambda acc, e: acc + "|" + e, self.categories[name], "").strip("|")

    def build_attributes(self) -> None: ...


class ConstList:
    def build_exports(self, namespace: dict[str, Any]) -> None:
        classes: list[str] = []
        for e in dir(self):
            if isinstance(getattr(self, e), type) and e != "__class__":
                classes.append(e)
        for cl in classes:
            namespace[cl.upper()] = getattr(self, cl)()
