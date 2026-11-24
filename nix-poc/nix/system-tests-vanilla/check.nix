# Fails, saying to regenerate the lock, when ./lock/*.json no longer matches the system-tests
# checkout (./check.py). Cheap: it only imports system-tests' scenario definitions. The core
# (./core.nix) depends on it, so a run never starts on a stale lock.
{
  runCommand,
  runner,
  systemTestsSrc,
}:
runCommand "system-tests-vanilla-lock-check"
  {
    nativeBuildInputs = [ runner ];
  }
  ''
    export HOME=$TMPDIR
    cd ${systemTestsSrc}
    python -I ${./check.py} ${./lock} ${./scenario_images.py}
    touch $out
  ''
