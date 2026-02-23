from functools import reduce
from pathlib import Path
from typing import Any

import yaml


def load(path: Path) -> dict[str, set[str]]:
    content = yaml.safe_load(path.read_text())
    groups: dict[str, set[str]] = {"all": set()}
    for element, element_cats in content.items():
        groups["all"].add(element)
        for category in element_cats:
            if category not in groups:
                groups[category] = set()
            groups[category].add(element)
    return groups


class Const:
    groups: dict[str, set[str]]
    _path: Path

    def __init__(self) -> None:
        self.groups = load(self._path)
        self._build_attributes()

    def _shell_export(self, name: str) -> str:
        return reduce(lambda acc, e: acc + "|" + e, sorted(self.groups[name]), "").strip("|")

    def _build_attributes(self) -> None: ...


class ConstList:
    def build_exports(self, namespace: dict[str, Any]) -> None:
        classes: list[str] = []
        for e in dir(self):
            if isinstance(getattr(self, e), type) and e != "__class__":
                classes.append(e)
        for cl in classes:
            namespace[cl.upper()] = getattr(self, cl)()
