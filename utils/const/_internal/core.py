from functools import reduce


class ConstGroup(set):
    name: str

    def init(self, name: str) -> None:
        self.name = name


class ConstGroups:
    groups: dict[str, ConstGroup]
    all = ConstGroup()

    def __init__(self) -> None:
        self.groups = {}
        for group_name in [att for att in dir(self) if isinstance(getattr(self, att), ConstGroup)]:
            self.groups[group_name] = getattr(self, group_name)
            self.groups[group_name].init(group_name)

        items = self._items()
        for item, groups in items.items():
            for group in groups:
                self.groups[group.name].add(item)
            self.groups["all"].add(item)

    def _items(self) -> dict[str, list[ConstGroup]]:
        return {}

    def _shell_export(self, group: str) -> str:
        return reduce(lambda acc, e: acc + "|" + e, sorted(getattr(self, group)), "").strip("|")
