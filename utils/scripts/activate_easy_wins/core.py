from __future__ import annotations

import copy
from utils._decorators import CustomSpec
from utils.scripts.activate_easy_wins.manifest_editor import ManifestEditor

from .types import Context


def update_manifest(manifest_editor: ManifestEditor, test_data: dict[Context, list[str]]) -> None:
    for context, rules in test_data.items():
        manifest_editor.set_context(context)

        for rule in rules:
            matches = manifest_editor.get_matches(rule)

            for match in matches:
                if match.clause_key == "*":
                    manifest_editor.update(match, f"v{context.library_version}", append_key=context.variant)
                else:
                    manifest_editor.update(match, f"v{context.library_version}")
