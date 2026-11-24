# The profiler's native code. libdd_wrapper links the Rust module; _ddup, _stack and _memalloc link
# libdd_wrapper. Each links against an interface stub of its dependency, so an implementation-only
# change to a library does not relink the extensions above it.
{
  lib,
  root,
  common,
  python,
  native,
  abseil,
  helpers,
}:
let
  profilingDir = root + "/ddtrace/internal/datadog/profiling";
  inPackage = "ddtrace/internal/datadog/profiling";

  # Profiling headers included across projects.
  sharedHeaders = [
    (profilingDir + "/cmake")
    (profilingDir + "/dd_wrapper/include")
    (profilingDir + "/profiling_helpers")
  ];

  # ddup, stack and FindLibNative.cmake read the Rust headers from the per-interpreter cargo target
  # directory setup.py uses.
  rustHeadersInTree = ''
    mkdir -p "src/native/target$PY_MAJMIN"
    cp -r --no-preserve=mode ${native.headers} "src/native/target$PY_MAJMIN/include"
  '';
  withPythonVars = script: common.pythonVars python + script;

  wrapperFlags = wrapper: [
    "-DDD_WRAPPER_DIR=${wrapper}/${inPackage}"
    "-DRUST_GENERATED_HEADERS_DIR=${native.headers}"
  ];

  dd-wrapper = helpers.mkCMakeExtension {
    pname = "ddtrace-dd-wrapper";
    dir = inPackage;
    basename = "libdd_wrapper";
    sourceDir = "ddtrace/internal/datadog/profiling/dd_wrapper";
    files = sharedHeaders ++ [
      (lib.fileset.difference (profilingDir + "/dd_wrapper") (profilingDir + "/dd_wrapper/test"))
    ];
    cmakeFlags = [
      "-DNATIVE_EXTENSION_LOCATION=${native.stub}/ddtrace/internal/native"
      "-DRUST_GENERATED_HEADERS_DIR=${native.headers}"
    ];
    linkOnly = [ native.stub ];
    preConfigure = withPythonVars rustHeadersInTree;
  };

  dd-wrapper-stub = helpers.mkInterfaceStub "ddtrace-dd-wrapper" dd-wrapper;

  ddup = helpers.mkCMakeExtension {
    pname = "ddtrace-ddup";
    dir = "${inPackage}/ddup";
    basename = "_ddup";
    sourceDir = "ddtrace/internal/datadog/profiling/ddup";
    files = sharedHeaders ++ [
      (profilingDir + "/ddup/CMakeLists.txt")
      (profilingDir + "/ddup/_ddup.pyx")
    ];
    cmakeFlags = wrapperFlags dd-wrapper-stub;
    linkOnly = [ dd-wrapper-stub ];
    preConfigure = withPythonVars rustHeadersInTree;
  };

  stack = helpers.mkCMakeExtension {
    pname = "ddtrace-stack";
    dir = "${inPackage}/stack";
    basename = "_stack";
    sourceDir = "ddtrace/internal/datadog/profiling/stack";
    files = sharedHeaders ++ [
      (lib.fileset.difference (profilingDir + "/stack") (
        lib.fileset.unions [
          (profilingDir + "/stack/test")
          (lib.fileset.maybeMissing (profilingDir + "/stack/fuzz"))
          (lib.fileset.fileFilter (f: f.hasExt "py" || f.hasExt "pyi") (profilingDir + "/stack"))
        ]
      ))
    ];
    cmakeFlags = wrapperFlags dd-wrapper-stub;
    linkOnly = [ dd-wrapper-stub ];
    preConfigure = withPythonVars rustHeadersInTree;
  };

  memalloc = helpers.mkCMakeExtension {
    pname = "ddtrace-memalloc";
    dir = "ddtrace/profiling/collector";
    basename = "_memalloc";
    sourceDir = "ddtrace/profiling/collector";
    files = sharedHeaders ++ [
      (root + "/cmake/AbseilDep.cmake")
      (lib.fileset.fileFilter (
        f: f.name == "CMakeLists.txt" || f.hasExt "cpp" || f.hasExt "h" || f.hasExt "hpp"
      ) (root + "/ddtrace/profiling/collector"))
    ];
    cmakeFlags = wrapperFlags dd-wrapper-stub ++ [ "-DABSL_INSTALL_DIR=${abseil}" ];
    linkOnly = [ dd-wrapper-stub ];
  };
in
{
  inherit
    dd-wrapper
    dd-wrapper-stub
    ddup
    stack
    memalloc
    ;
}
