"""Repository-specific Import Linter contracts."""

from typing import TYPE_CHECKING, TypedDict, cast

from grimp import ImportGraph
from importlinter import Contract, ContractCheck, fields, output

if TYPE_CHECKING:
    from importlinter.domain.imports import ImportExpression


class _CrossTestImport(TypedDict):
    importer: str
    imported: str
    line_numbers: tuple[int, ...]


def _is_test_module(module: str) -> bool:
    return module.startswith("tests.") and module.rsplit(".", maxsplit=1)[-1].startswith("test_")


class NoCrossTestImportsContract(Contract):
    """Prevent test modules from importing other test modules directly."""

    ignore_imports = fields.SetField(subfield=fields.ImportExpressionField(), required=False)

    def check(self, graph: ImportGraph, verbose: bool) -> ContractCheck:  # noqa: ARG002, FBT001
        ignored_imports = self._resolve_ignored_imports(graph)
        existing_cross_test_imports: set[tuple[str, str]] = set()
        violations: list[_CrossTestImport] = []

        for importer in sorted(graph.modules):
            if not _is_test_module(importer):
                continue

            for imported in sorted(graph.find_modules_directly_imported_by(importer)):
                if not _is_test_module(imported) or importer == imported:
                    continue
                existing_cross_test_imports.add((importer, imported))
                if (importer, imported) in ignored_imports:
                    continue

                details = graph.get_import_details(importer=importer, imported=imported)
                violations.append(
                    {
                        "importer": importer,
                        "imported": imported,
                        "line_numbers": tuple(detail["line_number"] for detail in details),
                    }
                )

        unused_ignores = sorted(ignored_imports - existing_cross_test_imports)
        return ContractCheck(
            kept=not violations and not unused_ignores,
            metadata={"unused_ignores": unused_ignores, "violations": violations},
        )

    def render_broken_contract(self, check: ContractCheck) -> None:
        violations = cast("list[_CrossTestImport]", check.metadata["violations"])
        for violation in violations:
            lines = ", ".join(f"l.{line_number}" for line_number in violation["line_numbers"])
            output.print_error(
                f"{violation['importer']} imports {violation['imported']} ({lines})",
                bold=False,
            )

        unused_ignores = cast("list[tuple[str, str]]", check.metadata["unused_ignores"])
        for importer, imported in unused_ignores:
            output.print_error(f"Unused exception: {importer} -> {imported}", bold=False)

    def _resolve_ignored_imports(self, graph: ImportGraph) -> set[tuple[str, str]]:
        ignored_imports: set[tuple[str, str]] = set()
        expressions = cast("set[ImportExpression] | None", self.ignore_imports)

        for expression in expressions or set():
            importers = graph.find_matching_modules(expression.importer.expression)
            imported_modules = graph.find_matching_modules(expression.imported.expression)
            ignored_imports.update((importer, imported) for importer in importers for imported in imported_modules)

        return ignored_imports
