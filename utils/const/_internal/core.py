from functools import reduce


class ConstGroup(set):
    name: str

    def init(self, name: str) -> None:
        self.name = name


class ConstGroups:
    all = ConstGroup()

    def __init__(self) -> None:
        groups = {}
        for group_name in [att for att in dir(self) if isinstance(getattr(self, att), ConstGroup)]:
            groups[group_name] = getattr(self, group_name)
            groups[group_name].init(group_name)

        items = self._items()
        for item, item_groups in items.items():
            for group in item_groups:
                groups[group.name].add(item)
            groups["all"].add(item)

    def _items(self) -> dict[str, list[ConstGroup]]:
        return {}

    def _shell_export(self, group: str) -> str:
        return reduce(lambda acc, e: acc + "|" + e, sorted(getattr(self, group)), "").strip("|")
