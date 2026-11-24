# ruff: noqa: INP001, CPY001
"""Helpers of the KVM build probe (see ./probe.sh). Standard library only.

probe.py stamp PHASE RAW LOG   read `nix --log-format internal-json` output on stdin, append it
                               timestamped to RAW (jsonl), render it readable to LOG and stdout
probe.py kvm                   open /dev/kvm, ask for its API version and create a VM (ioctl)
probe.py fods PLAN             the fixed-output derivations among PLAN's "will be built"
probe.py fetched PLAN          the paths of PLAN's "will be fetched" (substitutions)
probe.py summary OUT_DIR       timings.txt, timings.tsv and vm-*.log from OUT_DIR's raw.jsonl,
                               phases.tsv and drvs.json
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STORE = re.compile(r"/nix/store/[a-z0-9]{32}-")
PLAN_HEADER = re.compile(r"^\s*(these|this) .* will be ")

# Activity and result types of Nix's internal-json logger (src/libutil/include/nix/util/logging.hh).
ACT = {
    100: "copy-path",
    101: "file-transfer",
    102: "realise",
    103: "copy-paths",
    104: "builds",
    105: "build",
    106: "optimise",
    107: "verify",
    108: "substitute",
    109: "query-path-info",
    110: "post-build-hook",
    111: "build-waiting",
    112: "fetch-tree",
}
RES_LOG_LINE = 101
RES_SET_PHASE = 104
RES_POST_BUILD_LOG_LINE = 107

KVM_GET_API_VERSION = 0xAE00
KVM_CREATE_VM = 0xAE01

Interval = tuple[float, float]


def out(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def short(path: str | None) -> str:
    return STORE.sub("", path or "")


def plan_section(plan: str, header: str) -> list[str]:
    paths: list[str] = []
    on = False
    for line in Path(plan).read_text().splitlines():
        if PLAN_HEADER.match(line):
            on = header in line
        elif on and line.startswith("  /nix/store/"):
            paths.append(line.strip())
    return paths


def cmd_stamp(phase: str, raw: str, log: str) -> None:
    acts: dict[int, tuple[str, str, float]] = {}
    t0 = time.time()
    with Path(raw).open("a") as rawf, Path(log).open("a") as logf:

        def emit(t: float, text: str) -> None:
            line = f"[{time.strftime('%H:%M:%S', time.gmtime(t))} +{t - t0:7.1f}s {phase}] {text}"
            out(line)
            logf.write(line + "\n")

        for raw_line in sys.stdin:
            t = time.time()
            line = raw_line.rstrip("\n")
            if not line.startswith("@nix "):
                rawf.write(json.dumps({"t": t, "phase": phase, "text": line}) + "\n")
                emit(t, ANSI.sub("", line))
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                emit(t, line)
                continue
            ev["t"], ev["phase"] = t, phase
            rawf.write(json.dumps(ev) + "\n")
            action = ev.get("action")
            if action == "msg":
                emit(t, ANSI.sub("", ev.get("msg", "")))
            elif action == "start":
                kind = ACT.get(ev.get("type"), "")
                fields = ev.get("fields") or []
                name = short(fields[0]) if kind in ("build", "substitute") and fields else ""
                acts[ev["id"]] = (kind, name, t)
                if kind in ("build", "substitute", "fetch-tree") or (kind == "file-transfer" and ev.get("text")):
                    emit(t, f"start {kind} {name or ANSI.sub('', ev.get('text', ''))}")
            elif action == "stop":
                kind, name, start = acts.pop(ev.get("id"), ("", "", t))
                if kind in ("build", "substitute"):
                    emit(t, f"done  {kind} {name} ({t - start:.1f}s)")
            elif action == "result":
                kind, name, _ = acts.get(ev.get("id"), ("", "", t))
                rtype, fields = ev.get("type"), ev.get("fields") or []
                if rtype in (RES_LOG_LINE, RES_POST_BUILD_LOG_LINE) and fields:
                    emit(t, f"{name}> {ANSI.sub('', str(fields[0]))}")
                elif rtype == RES_SET_PHASE and fields:
                    emit(t, f"{name}: phase {fields[0]}")


def cmd_kvm() -> None:
    fd = os.open("/dev/kvm", os.O_RDWR | os.O_CLOEXEC)
    out(f"/dev/kvm opened, KVM_GET_API_VERSION = {fcntl.ioctl(fd, KVM_GET_API_VERSION)}")
    vm = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
    out(f"KVM_CREATE_VM ok (fd {vm})")
    os.close(vm)
    os.close(fd)


def cmd_fods(plan: str) -> None:
    built = plan_section(plan, "will be built")
    if not built:
        return
    shown = subprocess.run(["nix", "derivation", "show", *built], check=True, capture_output=True, text=True).stdout
    drvs = json.loads(shown)
    drvs = drvs.get("derivations", drvs)
    for key, drv in sorted(drvs.items()):
        if any("hash" in o for o in drv.get("outputs", {}).values()):
            out(key if key.startswith("/") else "/nix/store/" + key)


def cmd_fetched(plan: str) -> None:
    for p in plan_section(plan, "will be fetched"):
        out(p)


def intervals_union(iv: list[Interval]) -> float:
    total, end = 0.0, None
    for s, e in sorted(iv):
        if end is None or s > end:
            total += e - s
            end = e
        elif e > end:
            total += e - end
            end = e
    return total


def drv_categories(d: Path) -> dict[str, str]:
    """Derivation name (`<name>.drv`) -> vm-image, fod or build."""
    categories: dict[str, str] = {}
    try:
        drvs = json.loads((d / "drvs.json").read_text())
    except (OSError, ValueError):
        return categories
    for key, drv in drvs.get("derivations", drvs).items():
        sa = drv.get("structuredAttrs") or {}
        feats = sa.get("requiredSystemFeatures") or drv.get("env", {}).get("requiredSystemFeatures") or []
        if isinstance(feats, str):
            feats = feats.split()
        fod = any("hash" in o for o in drv.get("outputs", {}).values())
        category = "vm-image" if "kvm" in feats else "fod" if fod else "build"
        categories[short("/nix/store/" + key.split("/")[-1])] = category
    return categories


def cmd_summary(out_dir: str) -> None:
    d = Path(out_dir)
    categories = drv_categories(d)

    acts: dict[int, dict[str, Any]] = {}
    vm_logs: dict[str, tuple[float, list[tuple[float, str]]]] = {}
    rows: list[dict[str, Any]] = []
    for line in (d / "raw.jsonl").read_text().splitlines():
        ev = json.loads(line)
        action = ev.get("action")
        if action == "start":
            fields = ev.get("fields") or []
            acts[ev["id"]] = {
                "kind": ACT.get(ev.get("type"), ""),
                "name": short(fields[0]) if fields and isinstance(fields[0], str) else ev.get("text", ""),
                "start": ev["t"],
                "phase": ev["phase"],
                "text": ev.get("text", ""),
            }
        elif action == "stop" and ev.get("id") in acts:
            act = acts.pop(ev["id"])
            act["end"] = ev["t"]
            if act["kind"] in ("build", "substitute", "file-transfer", "fetch-tree"):
                act["category"] = categories.get(act["name"], "build") if act["kind"] == "build" else act["kind"]
                rows.append(act)
        elif action == "result" and ev.get("type") == RES_LOG_LINE and ev.get("id") in acts:
            act = acts[ev["id"]]
            if categories.get(act["name"]) == "vm-image":
                text = str((ev.get("fields") or [""])[0])
                vm_logs.setdefault(act["name"], (act["start"], []))[1].append((ev["t"], text))

    phases: list[tuple[str, float, float, str]] = []
    phases_file = d / "phases.tsv"
    if phases_file.exists():
        for line in phases_file.read_text().splitlines():
            name, s, e, rc = line.split("\t")
            phases.append((name, float(s), float(e), rc))

    with (d / "timings.tsv").open("w") as f:
        f.write("phase\tcategory\tname\tstart\tend\tseconds\n")
        f.writelines(
            "\t".join((r["phase"], r["category"], r["name"], f"{r['start']:.3f}", f"{r['end']:.3f}"))
            + f"\t{r['end'] - r['start']:.1f}\n"
            for r in sorted(rows, key=lambda r: r["start"])
        )

    for name, (start, lines) in vm_logs.items():
        with (d / f"vm-{name}.log").open("w") as f:
            f.writelines(f"+{t - start:8.1f}s {ANSI.sub('', text)}\n" for t, text in lines)

    report: list[str] = []
    if phases:
        t0 = phases[0][1]
        report.append("== Phases (wall clock)")
        report.extend(f"  {name:<16} {e - s:8.1f}s   (+{s - t0:7.1f}s)  exit {rc}" for name, s, e, rc in phases)
        report.extend((f"  {'total':<16} {phases[-1][2] - t0:8.1f}s", ""))

    report.append("== Activities by category: count, sum of durations, wall time covered (union)")
    cats: dict[str, list[Interval]] = {}
    for r in rows:
        cats.setdefault(r["category"], []).append((r["start"], r["end"]))
    report.extend(
        f"  {cat:<14} {len(iv):5d}  sum {sum(e - s for s, e in iv):8.1f}s  wall {intervals_union(iv):8.1f}s"
        for cat, iv in sorted(cats.items())
    )
    report.extend(("", "== Activities by phase and category (wall time covered)"))
    by: dict[tuple[str, str], list[Interval]] = {}
    for r in rows:
        by.setdefault((r["phase"], r["category"]), []).append((r["start"], r["end"]))
    report.extend(
        f"  {ph:<16} {cat:<14} {len(iv):5d}  wall {intervals_union(iv):8.1f}s" for (ph, cat), iv in sorted(by.items())
    )
    report.append("")

    for cat, n in (("vm-image", 10), ("build", 25), ("fod", 25), ("substitute", 15), ("fetch-tree", 15)):
        sel = sorted((r for r in rows if r["category"] == cat), key=lambda r: r["start"] - r["end"])[:n]
        if sel:
            report.append(f"== Longest {cat} (top {n})")
            report.extend(f"  {r['end'] - r['start']:8.1f}s  {r['phase']:<14} {r['name'] or r['text']}" for r in sel)
            report.append("")

    text = "\n".join(report)
    (d / "timings.txt").write_text(text + "\n")
    out(text)


def main() -> None:
    cmd, *args = sys.argv[1:]
    cmds: dict[str, Callable[..., None]] = {
        "stamp": cmd_stamp,
        "kvm": cmd_kvm,
        "fods": cmd_fods,
        "fetched": cmd_fetched,
        "summary": cmd_summary,
    }
    cmds[cmd](*args)


if __name__ == "__main__":
    main()
