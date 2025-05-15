from pathlib import Path
import json
from typing import Any
from utils import context


def generate_compliance_report(
    category: str,
    name: str,
    missing: list[str] | None = None,
    deprecated: list[str] | None = None,
) -> None:
    report: dict[str, Any] = {
        "framework": name,
        "language": context.library.name,
        "status": "pass" if not missing else "fail",
    }

    if deprecated:
        report["deprecated_attributes"] = deprecated
    if missing:
        report["missing_attributes"] = missing

    report_dir = Path(context.scenario.host_log_folder) / "compliance_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    file_path = report_dir / f"{category}_{name}.json"
    with open(file_path, "w") as f:
        json.dump(report, f, indent=2)
