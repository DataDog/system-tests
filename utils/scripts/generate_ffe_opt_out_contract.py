"""Generate runtime fixtures from the pinned, checked Lean policy oracle."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any


POLICY_CASE_COUNT = 90
CONTRACT_COMMIT = "f8a4176cd8360b12b56a8b6ec6ef215e2cc21077"
CONTRACT_MANIFEST_SHA256 = "15f68a067872c0f11dd494586eab32116b6dddae42754a2870375f85b55327f4"
SOURCE_FILES = (
    "lean/Contract.lean",
    "lean/Proofs.lean",
    "lean/Oracle.lean",
    "lean/Review.lean",
    "corpus/browser-proposal.jsonl",
)
DESTINATION = Path(__file__).resolve().parents[2] / "tests/ffe/fixtures/experimentation-opt-out-lean"
ATTRIBUTE = "dd_experimentation_opt_out_at"
CUTOFF = "2026-02-01T00:00:00.000000002Z"
ACTIVATION = {
    "missing": None,
    "invalid": "not-a-date",
    "before": "2026-02-01T00:00:00.000000001Z",
    "equal": CUTOFF,
    "after": "2026-02-01T00:00:00.000000003Z",
}
POLICY_THEOREMS = (
    "disabled_preserves_evaluation",
    "absent_preserves_evaluation",
    "invalid_context_precedes_activation",
    "immediate_ignores_activation",
    "invalid_activation_fails_future_flag_even_without_logging",
    "only_future_cutoff_needs_activation",
    "before_cutoff_retains_experiment",
    "equality_excludes_experiment",
    "missing_excludes_experiment",
    "ordinary_allocation_never_excluded",
)
INVALID_VALUES: dict[str, Any] = {
    "null": None,
    "true": True,
    "false": False,
    "zero": 0,
    "one": 1,
    "float": 1.5,
    "array": [CUTOFF],
    "object": {"timestamp": CUTOFF},
    "empty": "",
    "whitespace": " " + CUTOFF,
}
LOOKUP_CASE_COUNT = 9
LOOKUP_THEOREMS = ("invalid_context_precedes_lookup", "disabled_ignores_invalid_attribute")
LOOKUP_ORACLE = """import Lean
import Review
open Lean PR423 GoReview

def main : IO Unit := do
  let stdout ← IO.getStdout
  for (modeName, mode) in [("disabled", Mode.disabled), ("immediate", Mode.immediate),
      ("future_experiments_only", Mode.future)] do
    for (attributeName, attr) in [("absent", Attribute.absent), ("valid", Attribute.valid),
        ("invalid", Attribute.invalid)] do
      let error := match resolveReady mode attr false with
        | .invalidContext => "INVALID_CONTEXT"
        | .flagNotFound => "FLAG_NOT_FOUND"
        | .evaluate => "NONE"
      stdout.putStrLn ((Json.mkObj [("mode", toJson modeName), ("attribute", toJson attributeName),
        ("error", toJson error)]).compress)
"""


def materialize_lookup(row: dict[str, Any]) -> dict[str, Any]:
    flag = f"lean-missing-{row['mode']}-{row['attribute']}"
    attributes = (
        {} if row["attribute"] == "absent" else {ATTRIBUTE: CUTOFF if row["attribute"] == "valid" else "not-a-date"}
    )
    return {
        "id": f"lookup/{row['mode']}/{row['attribute']}",
        "decision_ids": ["D016"],
        "mode": row["mode"],
        "flag": flag,
        "subject": "subject-" + flag,
        "attributes": attributes,
        "defaultValue": "same-value",
        "expected": {
            "value": "same-value",
            "errorCode": row["error"],
            "reason": "ERROR",
            "variant": None,
            "allocationKey": None,
            "exposure": False,
        },
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allocation(key: str, variant: str, *, do_log: bool, serial_id: int) -> dict[str, Any]:
    return {
        "key": key,
        "rules": [],
        "splits": [{"variationKey": variant, "shards": [], "serialId": serial_id}],
        "doLog": do_log,
    }


def materialize(row: dict[str, Any], shape: str) -> dict[str, Any]:
    """Bind one abstract policy result to a known candidate and ordinary fallback.

    Assignment serialization is a harness obligation. It is not a Lean refinement proof.
    Equal values intentionally prevent a value-only assertion from passing this suite.
    """
    args = row["args"]
    flag = "lean-opt-out-" + row["id"].removeprefix("policy/").replace("/", "-") + "-" + shape
    candidate = allocation("candidate", "candidate-variant", do_log=args["doLog"], serial_id=101)
    if args["activation"] != "missing" or shape == "null-activation":
        candidate["randomizationActivatedAt"] = ACTIVATION[args["activation"]]
    ordinary = allocation("ordinary", "ordinary-variant", do_log=False, serial_id=102)
    allocations = [candidate] if shape == "no-fallback" else [candidate, ordinary]
    if shape == "unreachable-activation":
        allocations = [ordinary, candidate]
    attributes = (
        {} if args["attribute"] == "absent" else {ATTRIBUTE: CUTOFF if args["attribute"] == "valid" else "not-a-date"}
    )
    if shape.startswith("invalid-type-"):
        attributes[ATTRIBUTE] = INVALID_VALUES[shape.removeprefix("invalid-type-")]
    if shape in {"targeting-match", "targeting-miss"}:
        # Native targeting remains in force after the policy decision. The
        # match case also detects removal of the customer attribute.
        candidate["rules"] = [
            {
                "conditions": [
                    {
                        "attribute": ATTRIBUTE,
                        "operator": "ONE_OF",
                        "value": [CUTOFF if shape == "targeting-match" else "different"],
                    }
                ]
            }
        ]
    error = row["expected"]["error"]
    selected = None
    if error == "NONE":
        if shape in {"unreachable-activation", "targeting-miss"}:
            selected = ordinary
        elif not row["expected"]["exclude"]:
            selected = candidate
        elif shape != "no-fallback":
            selected = ordinary
    expected = {
        "value": "same-value",
        "errorCode": None if error == "NONE" else error,
        "reason": "ERROR"
        if error != "NONE"
        else "TARGETING_MATCH"
        if selected is candidate and shape == "targeting-match"
        else "STATIC"
        if selected
        else "DEFAULT",
        "variant": selected["splits"][0]["variationKey"] if selected else None,
        "allocationKey": selected["key"] if selected else None,
        "exposure": selected["doLog"] if selected else False,
    }
    return {
        "id": row["id"] + "/" + shape,
        "oracle_case_id": row["id"],
        "decision_ids": row["decision_ids"],
        "mode": args["mode"],
        "shape": shape,
        "flag": flag,
        "subject": "subject-" + flag,
        "attributes": attributes,
        "defaultValue": "same-value",
        "expected": expected,
        "configuration": {
            "key": flag,
            "enabled": True,
            "variationType": "STRING",
            "variations": {
                key: {"key": key, "value": "same-value"} for key in ["candidate-variant", "ordinary-variant"]
            },
            "allocations": allocations,
        },
    }


def generate(source: Path, lean: Path) -> dict[str, bytes]:
    manifest_path = source / "manifest.json"
    if sha256(manifest_path) != CONTRACT_MANIFEST_SHA256:
        raise ValueError("Unreviewed contract manifest")
    manifest = json.loads(manifest_path.read_text())
    for name in SOURCE_FILES:
        if sha256(source / name) != manifest["files"][name]:
            raise ValueError(f"Changed contract source: {name}")
    version = subprocess.check_output([str(lean), "--version"], text=True).strip()
    if not re.search(r"\bversion 4\.19\.0\b", version):
        raise ValueError(f"Expected Lean 4.19.0; got {version}")
    rows = [json.loads(line) for line in (source / "corpus/browser-proposal.jsonl").read_text().splitlines()]
    rows = [row for row in rows if row["kind"] == "policy"]
    if len(rows) != POLICY_CASE_COUNT or len({row["id"] for row in rows}) != POLICY_CASE_COUNT:
        raise ValueError("Expected all 90 policy cases")
    with tempfile.TemporaryDirectory(prefix="ffe-runtime-oracle-") as temporary:
        build = Path(temporary)
        env = {**os.environ, "LEAN_PATH": str(build)}
        for name in ["Contract", "Proofs", "Oracle", "Review"]:
            shutil.copyfile(source / f"lean/{name}.lean", build / f"{name}.lean")
            result = subprocess.run(
                [str(lean), "-o", f"{name}.olean", f"{name}.lean"],
                cwd=build,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            if "warning:" in result.stdout + result.stderr or "sorry" in result.stdout + result.stderr:
                raise ValueError("Lean compilation emitted a warning or proof hole")
        audit = (
            "import Proofs\nimport Review\n"
            + "\n".join(
                [f"#print axioms PR423.{name}" for name in POLICY_THEOREMS]
                + [f"#print axioms GoReview.{name}" for name in LOOKUP_THEOREMS]
            )
            + "\n"
        )
        (build / "Audit.lean").write_text(audit)
        audit_output = subprocess.check_output([str(lean), "Audit.lean"], cwd=build, env=env, text=True)
        for axioms in re.findall(r"depends on axioms: \[([^]]*)\]", audit_output):
            if set(axioms.split(", ")) - {"propext", "Quot.sound"}:
                raise ValueError("Unexpected Lean axiom")
        requests = (
            "\n".join(
                json.dumps({k: v for k, v in row.items() if k not in {"expected", "decision_ids"}}) for row in rows
            )
            + "\n"
        )
        output = subprocess.check_output(
            [str(lean), "--run", "Oracle.lean"], cwd=build, env=env, input=requests, text=True
        )
        (build / "LookupOracle.lean").write_text(LOOKUP_ORACLE)
        lookup_output = subprocess.check_output(
            [str(lean), "--run", "LookupOracle.lean"], cwd=build, env=env, text=True
        )
    observed = [json.loads(line) for line in output.splitlines()]
    if len(observed) != POLICY_CASE_COUNT or {row["id"]: row["observed"] for row in observed} != {
        row["id"]: row["expected"] for row in rows
    }:
        raise ValueError("Lean output differs from the pinned policy corpus")
    by_id = {row["id"]: row["observed"] for row in observed}
    lookup_rows = [json.loads(line) for line in lookup_output.splitlines()]
    if len(lookup_rows) != LOOKUP_CASE_COUNT:
        raise ValueError("Expected all nine ready-provider lookup cases")
    cases: list[dict[str, Any]] = []
    for original in rows:
        row = {**original, "expected": by_id[original["id"]]}
        shapes = ["fallback", "no-fallback"]
        if row["args"]["activation"] == "missing":
            shapes.append("null-activation")
        if row["args"]["activation"] == "invalid":
            shapes.append("unreachable-activation")
        if row["args"]["activation"] == "before" and row["args"]["doLog"]:
            if row["args"]["attribute"] == "invalid":
                shapes.extend("invalid-type-" + name for name in INVALID_VALUES)
            if row["args"]["attribute"] == "valid":
                shapes.extend(["targeting-match", "targeting-miss"])
        cases.extend(materialize(row, shape) for shape in shapes)
    artifacts = {
        "runtime-cases.json": (json.dumps(cases, indent=2) + "\n").encode(),
        "policy-oracle.jsonl": output.encode(),
        "policy-axioms.txt": audit_output.encode(),
        "lookup-oracle.jsonl": lookup_output.encode(),
        "lookup-cases.json": (json.dumps([materialize_lookup(row) for row in lookup_rows], indent=2) + "\n").encode(),
        "lean/LookupOracle.lean": LOOKUP_ORACLE.encode(),
        **{name: (source / name).read_bytes() for name in SOURCE_FILES},
    }
    provenance = {
        "repository": "https://github.com/DataDog/ffe-system-test-data",
        "commit": CONTRACT_COMMIT,
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "contract_path": "contracts/experimentation-opt-out",
        "policy_case_count": POLICY_CASE_COUNT,
        "runtime_case_count": len(cases),
        "theorems": list(POLICY_THEOREMS),
        "lookup_theorems": list(LOOKUP_THEOREMS),
        "lookup_case_count": LOOKUP_CASE_COUNT,
        "decision_revisions": {"D002": 1, "D004": 2, "D010": 1, "D011": 1, "D016": 1},
        "source_files": {name: manifest["files"][name] for name in SOURCE_FILES},
        "files": {name: hashlib.sha256(contents).hexdigest() for name, contents in artifacts.items()},
        "limits": (
            "Policy outputs come from Lean. UFC/context materialization, public API details, "
            "transport, telemetry and lifecycle require native execution. Browser timestamp grammar, "
            "acknowledgement, compiler and operation-count profiles are not asserted."
        ),
    }
    artifacts["SOURCE.json"] = (json.dumps(provenance, indent=2) + "\n").encode()
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-root", type=Path, required=True)
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    artifacts = generate(args.contract_root.resolve(), args.lean.resolve())
    for name, content in artifacts.items():
        path = DESTINATION / name
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                raise ValueError(f"Generated contract drift: {name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    runtime_count = json.loads(artifacts["SOURCE.json"])["runtime_case_count"]
    print(f"Verified {POLICY_CASE_COUNT} Lean policy outputs and {runtime_count} runtime cases")


if __name__ == "__main__":
    main()
