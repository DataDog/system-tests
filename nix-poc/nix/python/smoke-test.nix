# tests/smoke_test.py, the check CI runs on every built wheel, against the installed package.
{
  runCommand,
  common,
  root,
  python,
  python-package,
}:
runCommand "ddtrace-smoke-test-${common.version}"
  (
    {
      nativeBuildInputs = [ (python.withPackages (_: [ python-package ])) ];
    }
    // common.caAttrs
  )
  ''
    cd "$TMPDIR"
    python ${root + "/tests/smoke_test.py"}
    touch "$out"
  ''
