# The IAST taint-tracking extension (pybind11 + abseil).
{
  lib,
  root,
  abseil,
  helpers,
}:
let
  dir = root + "/ddtrace/appsec/_iast/_taint_tracking";
in
helpers.mkCMakeExtension {
  pname = "ddtrace-iast-taint-tracking";
  dir = "ddtrace/appsec/_iast/_taint_tracking";
  basename = "_native";
  sourceDir = "ddtrace/appsec/_iast/_taint_tracking";
  files = [
    (root + "/cmake/AbseilDep.cmake")
    (dir + "/_vendor/pybind11")
    (lib.fileset.difference (lib.fileset.fileFilter (
      f: f.name == "CMakeLists.txt" || f.hasExt "cpp" || f.hasExt "h"
    ) dir) (lib.fileset.unions [ (dir + "/tests") (dir + "/_vendor") ]))
  ];
  cmakeFlags = [
    "-DNATIVE_TESTING=OFF"
    "-DABSL_INSTALL_DIR=${abseil}"
  ];
}
