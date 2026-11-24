# The pure-Python part of the wheel: what setuptools' find_packages() and package_data select in
# setup.py, without any compiled artifact. Shared by every interpreter.
{
  lib,
  stdenvNoCC,
  python3,
  common,
  root,
}:
let
  ddtrace = root + "/ddtrace";
in
stdenvNoCC.mkDerivation (
  {
    pname = "ddtrace-python-sources";
    inherit (common) version;

    src = common.src [
      (lib.fileset.fileFilter (f: f.hasExt "py" || f.hasExt "pyi" || f.name == "py.typed") ddtrace)
      (ddtrace + "/appsec/rules.json")
      (ddtrace + "/appsec/sca/_cve_data.json")
      (ddtrace + "/internal/third-party.tar.gz")
    ];

    nativeBuildInputs = [ (python3.withPackages (ps: [ ps.setuptools ])) ];

    dontConfigure = true;
    dontFixup = true;

    buildPhase = ''
      runHook preBuild
      python ${./scripts/select_python_sources.py} . "$out"
      runHook postBuild
    '';
  }
  // common.caAttrs
)
