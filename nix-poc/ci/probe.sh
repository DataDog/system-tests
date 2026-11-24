#!/usr/bin/env bash
# Throwaway probe: time a cold build of the hermetic system-tests package (dd-trace-ops'
# system-tests-vanilla, copied in ../) on the KVM GitLab runner pool, every image built in a VM.
# Builds, never runs. Run from the repository root by .gitlab-ci.yml; writes to $OUT.
# PROBE_STOP_AFTER=<phase> stops after that phase (to try it locally).
#
# Phases (each timed, see $OUT/phases.tsv and $OUT/timings.txt):
#   node        what the job runs on, /dev/kvm
#   inputs      fetch the flake inputs (nix flake archive)
#   tools       python3 for ./probe.py (substituted)
#   eval        evaluate the target, dump its derivation graph
#   plan        dry run: what will be built, what will be substituted
#   substitute  every path the plan fetches from cache.nixos.org
#   fetch       every fixed-output derivation the plan builds (wheels, image pulls, sources)
#   runner      the test runner's venv
#   image-base  the base image plus /etc/pip.conf, built in a VM
#   image-web   the weblog image, built in a VM
#   final       the final package (runs.DEFAULT.fastapi)
set -euo pipefail

ROOT="$(pwd)"
FLAKE="path:$ROOT/nix-poc"
SCOPE="legacyPackages.x86_64-linux.system-tests-vanilla.imagesInVM"
TARGET="$SCOPE.runs.DEFAULT.fastapi"
OUT="${OUT:-$ROOT/probe-out}"
PROBE="$ROOT/nix-poc/ci/probe.py"
mkdir -p "$OUT"
: > "$OUT/phases.tsv"
: > "$OUT/raw.jsonl"
: > "$OUT/build.log"

now() { date +%s.%N; }
# dur START END: END - START (both from now()), in seconds with one decimal.
dur() {
  local ms=$(((${2/./} - ${1/./}) / 1000000))
  printf '%d.%d' $((ms / 1000)) $((ms % 1000 / 100))
}

# phase NAME CMD...: run CMD, record its wall clock in phases.tsv. CMD runs in a `||` list, where
# `set -e` does not apply: phase functions check their commands themselves.
phase() {
  local name="$1" start end rc=0
  shift
  echo -e "\n\e[1;36m=== phase $name ($(date -u +%H:%M:%S))\e[0m"
  start="$(now)"
  "$@" || rc=$?
  end="$(now)"
  printf '%s\t%s\t%s\t%s\n' "$name" "$start" "$end" "$rc" >> "$OUT/phases.tsv"
  echo -e "\e[1;36m=== phase $name: $(dur "$start" "$end")s, exit $rc\e[0m"
  # For trying the script locally: stop after a given phase.
  if [ "$rc" = 0 ] && [ "${PROBE_STOP_AFTER:-}" = "$name" ]; then exit 0; fi
  return "$rc"
}

# nixlog PHASE NIXARGS...: a nix command, its log timestamped and parsed by probe.py.
nixlog() {
  local name="$1"
  shift
  nix --log-format internal-json -L "$@" 2>&1 | "$PY" "$PROBE" stamp "$name" "$OUT/raw.jsonl" "$OUT/build.log"
}

report() {
  local rc=$?
  set +e
  echo -e "\n\e[1;36m=== report\e[0m"
  if [ -e "$ROOT/result" ]; then
    nix path-info -rS "$ROOT/result" | sort -k2 -n > "$OUT/closure.txt"
    nix path-info -Sh "$ROOT/result" >> "$OUT/closure.txt"
    tail -n 15 "$OUT/closure.txt"
  fi
  du -sh /nix/store > "$OUT/store-size.txt" 2>&1
  cat "$OUT/store-size.txt"
  if [ -n "${PY:-}" ]; then
    "$PY" "$PROBE" summary "$OUT"
  else
    cat "$OUT/phases.tsv"
  fi
  exit "$rc"
}
trap report EXIT

node_info() {
  local cores quota period
  echo "runner: ${CI_RUNNER_DESCRIPTION:-?} (id ${CI_RUNNER_ID:-?}, tags ${CI_RUNNER_TAGS:-?})"
  echo "kernel: $(uname -a)"
  echo "nproc: $(nproc)"
  grep -m1 'model name' /proc/cpuinfo || true
  grep -m1 'vendor_id' /proc/cpuinfo || true
  echo "cpu flags: $(grep -m1 '^flags' /proc/cpuinfo | grep -o -w -E 'hypervisor|vmx|svm|ept|npt' | sort -u | tr '\n' ' ')"
  echo "  (hypervisor = this node is itself a VM, i.e. nested virtualization; none = metal)"
  grep -E 'MemTotal|MemAvailable' /proc/meminfo
  for f in sys_vendor product_name product_version board_name; do
    echo "dmi $f: $(cat /sys/class/dmi/id/$f 2>/dev/null || echo '?')"
  done
  if command -v systemd-detect-virt > /dev/null; then
    echo "systemd-detect-virt: $(systemd-detect-virt 2>&1 || true)"
  fi
  echo "cgroup cpu.max: $(cat /sys/fs/cgroup/cpu.max 2>/dev/null || echo '?')"
  echo "cgroup memory.max: $(cat /sys/fs/cgroup/memory.max 2>/dev/null || echo '?')"
  echo "disk: $(df -h /nix /tmp 2>/dev/null | tail -n +2 | tr -s ' ' | tr '\n' ';')"
  # EC2 instance type, if the pod may reach IMDS (often blocked).
  local token
  token="$(curl -fsS -m 2 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' 2>/dev/null || true)"
  if [ -n "$token" ]; then
    echo "ec2 instance-type: $(curl -fsS -m 2 -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/instance-type 2>/dev/null || echo '?')"
  else
    echo "ec2 instance-type: IMDS not reachable"
  fi
  ls -ln /dev/kvm || return
  if (exec 3<> /dev/kvm); then echo "/dev/kvm: opens read-write"; else echo "/dev/kvm: cannot open"; return 1; fi

  # Nix's `cores` (NIX_BUILD_CORES): nproc may be the whole node, so use the pod's CPU quota when
  # there is one. The image VMs do not use it: image-builder.nix does not set
  # enableParallelBuilding, so vmTools starts them with qemu's default of 1 vCPU (and 4 GiB of
  # memfd memory, which counts against the pod's memory limit).
  cores="$(nproc)"
  if read -r quota period < /sys/fs/cgroup/cpu.max 2>/dev/null && [ "$quota" != max ]; then
    cores=$(((quota + period - 1) / period))
  fi
  echo "nix cores: $cores (image VMs: 1 vCPU, 4 GiB)"
  echo "cores = $cores" >> "$OUT/nix.conf.extra"
}

tools() {
  # python3 from the flake's own nixpkgs, substituted from cache.nixos.org.
  local py
  py="$(nix build --no-link --print-out-paths --inputs-from "$FLAKE" nixpkgs#python3)" || return
  PY="$py/bin/python3"
  "$PY" --version || return
  "$PY" "$PROBE" kvm
}

evaluate() {
  DRV="$(nix eval --raw "$FLAKE#$TARGET.drvPath")" || return
  echo "target: $DRV"
  nix derivation show -r "$DRV" > "$OUT/drvs.json" || return
  echo "derivations in the graph: $("$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d.get("derivations", d)))' "$OUT/drvs.json")"
}

plan() {
  nix build --dry-run "$DRV^*" > "$OUT/plan.txt" 2>&1 || { cat "$OUT/plan.txt"; return 1; }
  grep -E 'will be (built|fetched)' "$OUT/plan.txt" || echo "nothing to build or fetch"
  "$PY" "$PROBE" fetched "$OUT/plan.txt" > "$OUT/plan-fetched.txt" || return
  "$PY" "$PROBE" fods "$OUT/plan.txt" > "$OUT/plan-fods.txt" || return
  echo "substitutions: $(wc -l < "$OUT/plan-fetched.txt"), fixed-output builds: $(wc -l < "$OUT/plan-fods.txt")"
}

substitute() {
  [ -s "$OUT/plan-fetched.txt" ] || return 0
  nixlog substitute build --no-link --keep-going --stdin < "$OUT/plan-fetched.txt"
}

fetch() {
  [ -s "$OUT/plan-fods.txt" ] || return 0
  # (the nixos/nix image has no sed or awk)
  while read -r drv; do echo "$drv^*"; done < "$OUT/plan-fods.txt" | nixlog fetch build --no-link --keep-going --stdin
}

build_attr() {
  local name="$1" attr="$2"
  shift 2
  nixlog "$name" build "$FLAKE#$attr" "$@"
}

export NIX_CONFIG
phase node node_info
NIX_CONFIG="$NIX_CONFIG
$(cat "$OUT/nix.conf.extra")"
echo "--- NIX_CONFIG"
echo "$NIX_CONFIG"
nix --version
nix config show > "$OUT/nix-config.txt"

phase inputs nix flake archive "$FLAKE"
phase tools tools
phase eval evaluate
phase plan plan
phase substitute substitute
phase fetch fetch
phase runner build_attr runner "$SCOPE.runner" --no-link
phase image-base build_attr image-base "$SCOPE.weblogs.fastapi.pipBase" --no-link
phase image-web build_attr image-web "$SCOPE.weblogs.fastapi" --no-link
phase final build_attr final "$TARGET" --out-link "$ROOT/result"
