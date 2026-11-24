# Abseil, built once per platform and shared by the IAST and memalloc extensions (setup.py's
# SHARED_DEPS). The commit comes from cmake/abseil/CMakeLists.txt; FetchContent is pointed at the
# pre-fetched source so the build never touches the network.
{
  lib,
  stdenv,
  cmake,
  common,
  root,
}:
let
  source = builtins.fetchGit {
    url = "https://github.com/abseil/abseil-cpp.git";
    inherit (common.abseil) rev;
    shallow = true;
  };
in
stdenv.mkDerivation (
  {
    pname = "ddtrace-abseil";
    version = common.abseil.tag;

    src = common.src [ (root + "/cmake/abseil") ];

    nativeBuildInputs = [ cmake ];

    cmakeDir = "../cmake/abseil";
    cmakeBuildType = "RelWithDebInfo";
    cmakeFlags = [
      (lib.cmakeFeature "FETCHCONTENT_SOURCE_DIR_ABSL" "${source}")
      (lib.cmakeBool "FETCHCONTENT_FULLY_DISCONNECTED" true)
      (lib.cmakeBool "CMAKE_POSITION_INDEPENDENT_CODE" true)
    ];
  }
  // common.caAttrs
)
