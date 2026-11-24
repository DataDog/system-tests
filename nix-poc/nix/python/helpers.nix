# Builders for the per-interpreter derivations. Every builder outputs a tree laid out like the wheel
# (ddtrace/...), so assembling the wheel is a plain merge of trees.
{
  lib,
  stdenv,
  runCommand,
  cmake,
  llvmPackages,
  patchelf,
  common,
  python,
  buildPython,
}:
let
  inherit (stdenv.hostPlatform) isLinux isDarwin;

  # Drop RUNPATH entries that point at link-time-only inputs (interface stubs, or on macOS the real
  # libraries the stubs would replace) and keep the $ORIGIN-relative entries the wheel layout relies
  # on. Store paths are kept only when they provide a DT_NEEDED library.
  fixupLinks = linkOnly: ''
    linkOnly=(${lib.concatMapStringsSep " " (d: ''"${d}"'') linkOnly})
    while IFS= read -r -d "" so; do
  ''
  + lib.optionalString isLinux ''
      needed="$(patchelf --print-needed "$so")"
      keep=()
      IFS=: read -ra entries <<< "$(patchelf --print-rpath "$so")"
      for entry in "''${entries[@]}"; do
        case "$entry" in
          '$ORIGIN'*) keep+=("$entry"); continue ;;
        esac
        for path in "''${linkOnly[@]}"; do
          [[ "$entry" == "$path"* ]] && continue 2
        done
        for lib in $needed; do
          if [ -e "$entry/$lib" ]; then keep+=("$entry"); break; fi
        done
      done
      patchelf --set-rpath "$(IFS=:; echo "''${keep[*]}")" "$so"
  ''
  + lib.optionalString isDarwin ''
      for path in "''${linkOnly[@]}"; do
        otool -l "$so" | awk '$1 == "path" { print $2 }' | while read -r rpath; do
          if [[ "$rpath" == "$path"* ]]; then install_name_tool -delete_rpath "$rpath" "$so"; fi
        done
      done
  ''
  + ''
    done < <(find "$out" -name '*.so' -print0)
  '';
in
{
  # Interface-only copy of a tree's shared libraries: just the dynamic symbol table, enough to link
  # against. Its content changes only when the exported interface does, so dependents stay cached
  # across implementation-only changes. On macOS the tree is returned as is.
  mkInterfaceStub =
    name: tree:
    if isLinux then
      runCommand "${name}-stub-${common.version}"
        (
          {
            nativeBuildInputs = [ llvmPackages.llvm ];
          }
          // common.caAttrs
        )
        ''
          cd ${tree}
          find . -name '*.so' | while read -r so; do
            mkdir -p "$out/$(dirname "$so")"
            llvm-ifs --input-format=ELF --output-elf="$out/$so" "$so"
          done
        ''
    else
      tree;

  # One CMake project from setup.py's CMakeExtension list (or libdd_wrapper), configured with the
  # arguments CustomBuildExt._get_common_cmake_args passes.
  mkCMakeExtension =
    {
      pname,
      # Directory of the output in the wheel, and the output file name without EXT_SUFFIX.
      dir,
      basename,
      # CMake source directory, relative to the repository root.
      sourceDir,
      files,
      cmakeFlags ? [ ],
      # Inputs only needed at link time; references to them are removed from the result.
      linkOnly ? [ ],
      preConfigure ? "",
    }:
    stdenv.mkDerivation (
      {
        inherit pname preConfigure;
        inherit (common) version stripDebugList;

        src = common.src files;

        nativeBuildInputs = [
          cmake
          buildPython
        ]
        ++ lib.optional isLinux patchelf;

        # Configured by hand below; the default hooks would rewrite RUNPATHs and install names.
        dontUseCmakeConfigure = true;
        dontPatchELF = true;
        NIX_NO_SELF_RPATH = true;

        cmakeExtraFlags = cmakeFlags;

        buildPhase = ''
          runHook preBuild
          ${common.pythonVars python}
          outdir="$out/${dir}"
          mkdir -p "$outdir"
          cmake -S "${sourceDir}" -B "$NIX_BUILD_TOP/cmake-build" \
            -DCMAKE_BUILD_TYPE=RelWithDebInfo \
            -DCMAKE_INSTALL_PREFIX="$NIX_BUILD_TOP/prefix" \
            -DPython3_ROOT_DIR=${python} \
            -DPython3_EXECUTABLE=${buildPython.interpreter} \
            -DPYTHON_EXECUTABLE=${buildPython.interpreter} \
            -DLIB_INSTALL_DIR="$outdir" \
            -DEXTENSION_NAME="${basename}$EXT_SUFFIX" \
            -DEXTENSION_SUFFIX="$EXT_SUFFIX" \
            -DCMAKE_MODULE_PATH="$PWD/cmake" \
            -DBUILD_TESTING=OFF \
            $cmakeExtraFlags
          cmake --build "$NIX_BUILD_TOP/cmake-build" --parallel "$NIX_BUILD_CORES"
          cmake --install "$NIX_BUILD_TOP/cmake-build"
          runHook postBuild
        '';

        dontInstall = true;

        postFixup = fixupLinks linkOnly;
      }
      // common.caAttrs
    );

  # Cython's .pyx -> .c step for one module, with the compile-time environment setup.py passes to
  # cythonize(). Only the .pyx and the .pxd declarations are inputs.
  mkCythonized =
    { module, files }:
    stdenv.mkDerivation (
      {
        pname = "ddtrace-cythonize-${module}";
        inherit (common) version;

        src = common.src files;

        nativeBuildInputs = [ buildPython ];

        dontConfigure = true;
        dontFixup = true;

        buildPhase = ''
          runHook preBuild
          python ${./scripts/cythonize_module.py} ${module} "$out"
          runHook postBuild
        '';
      }
      // common.caAttrs
    );

  # One setuptools Extension compiled with the interpreter's own flags, as setup.py's build_ext does.
  # `generated` trees (cythonized sources) are merged into the source tree first.
  mkSetuptoolsExtension =
    {
      module,
      sources,
      files ? [ ],
      generated ? [ ],
      extraCompileArgs ? [ ],
      defineMacros ? [ ],
      includeDirs ? [ ],
      libraries ? [ ],
    }:
    stdenv.mkDerivation (
      {
        pname = "ddtrace-ext-${module}";
        inherit (common) version stripDebugList;

        src = if files == [ ] then null else common.src files;
        dontUnpack = files == [ ];

        nativeBuildInputs = [ buildPython ];

        extensionSpec = builtins.toJSON {
          inherit
            module
            sources
            extraCompileArgs
            defineMacros
            includeDirs
            libraries
            ;
        };

        dontConfigure = true;

        buildPhase = ''
          runHook preBuild
          ${lib.concatMapStrings (tree: ''
            cp -rT --no-preserve=mode ${tree} .
          '') generated}
          python ${./scripts/build_extension.py} "$out"
          runHook postBuild
        '';

        dontInstall = true;
      }
      // common.caAttrs
    );
}
