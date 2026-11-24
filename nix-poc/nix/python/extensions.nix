# The setuptools-built extensions from setup.py: plain C/C++ modules and Cython modules. Each Cython
# module is two derivations: cythonize (.pyx -> .c) and compile (.c -> .so), so a .pyx edit that
# Cython turns into identical C does not recompile, and a header edit does not re-run Cython.
{
  lib,
  stdenv,
  root,
  python,
  helpers,
  native,
}:
let
  ddtrace = root + "/ddtrace";
  # Py_BUILD_CORE, as in setup.py's extra_compile_args for the C modules.
  coreArgs = [ "-DPy_BUILD_CORE" ];
  byteOrder = if stdenv.hostPlatform.isLittleEndian then "LITTLE" else "BIG";

  cExtensions = {
    "ddtrace.internal._threads" = {
      sources = [ "ddtrace/internal/_threads.cpp" ];
      extraCompileArgs = [
        "-std=c++20"
        "-Wall"
        "-Wextra"
      ];
    };
    "ddtrace.internal.security._stacktrace" = {
      sources = [ "ddtrace/internal/security/_stacktrace.c" ];
      extraCompileArgs = coreArgs;
    };
    "ddtrace.appsec._iast._ast.iastpatch" = {
      sources = [ "ddtrace/appsec/_iast/_ast/iastpatch.c" ];
      extraCompileArgs = coreArgs;
    };
  };

  cythonModules = {
    "ddtrace.internal._tagset" = { };
    "ddtrace.internal._encoding" = {
      headers = map (h: ddtrace + "/internal/${h}") [
        "_utils.h"
        "pack.h"
        "pack_template.h"
        "sysdep.h"
      ];
      includeDirs = [ "." ];
      defineMacros = [ [ "__${byteOrder}_ENDIAN__" "1" ] ];
    };
  }
  // lib.optionalAttrs native.profiling (
    lib.genAttrs [
      "ddtrace.profiling._threading"
      "ddtrace.profiling.collector._task"
      "ddtrace.profiling.collector._exception"
      "ddtrace.profiling.collector._fast_poisson"
      "ddtrace.profiling.collector._sampler"
      "ddtrace.profiling.collector._lock"
    ] (_: { })
  );

  modulePath = module: lib.replaceStrings [ "." ] [ "/" ] module;

  # Every .pxd is a cimport candidate, but no other module's .pyx.
  pxdFiles = lib.fileset.fileFilter (f: f.hasExt "pxd") ddtrace;

  cythonized = lib.mapAttrs (
    module: _:
    helpers.mkCythonized {
      inherit module;
      files = [
        pxdFiles
        (root + "/${modulePath module}.pyx")
      ];
    }
  ) cythonModules;

  compiledCython = lib.mapAttrs (
    module: spec:
    helpers.mkSetuptoolsExtension {
      inherit module;
      sources = [ "${modulePath module}.c" ];
      files = spec.headers or [ ];
      generated = [ cythonized.${module} ];
      includeDirs = spec.includeDirs or [ ];
      defineMacros = spec.defineMacros or [ ];
    }
  ) cythonModules;

  compiledC = lib.mapAttrs (
    module: spec:
    helpers.mkSetuptoolsExtension (
      {
        inherit module;
        files = map (s: root + "/${s}") spec.sources;
      }
      // spec
    )
  ) cExtensions;
in
{
  inherit cythonized;
  modules = compiledC // compiledCython;
}
