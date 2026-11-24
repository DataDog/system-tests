# The weblog image, built by system-tests' own `utils/build/build.sh` from the upstream Dockerfile,
# with no network. Two image derivations (./image-builder.nix: $out/image.tar, $out/image.json):
#
#   pipBase  the pinned base image plus /etc/pip.conf, the one deviation from upstream images:
#            `no-index`, `find-links` to the wheelhouse served during the weblog's build. It stays
#            in the weblog image, pointing to a server gone at run time; nothing pip installs then.
#   weblog   `build.sh python --weblog-variant <variant> --images weblog` on a copy of the
#            checkout, `docker save system_tests/weblog` (with the labels build.sh sets).
#
# What the build would fetch is in the store instead:
#
#   - the base image (`FROM system_tests_base_python_<variant>`, which build.sh passes as
#     `--build-context <alias>=docker-image://datadog/system-tests:<variant>.base-<hash>`): loaded
#     into the daemon, where BuildKit resolves the context from the local image store;
#   - what the Dockerfile `pip install`s: ddtrace (install_ddtrace.sh, from
#     binaries/python-load-from-pip, upstream's way of pinning a release) and the Dockerfile's own
#     pins, from a wheelhouse of hash-pinned PyPI wheels (./lock/weblog-<variant>.json), served
#     over HTTP on the daemon's bridge.
#
# build.sh builds Python weblogs for linux/amd64 unless told otherwise; it is given the host's
# platform (its --docker-platform option), so the weblog runs natively.
{
  lib,
  stdenv,
  python3,
  bash,
  coreutils,
  findutils,
  gnused,
  gnugrep,
  gawk,
  docker-client,
  fetchurl,
  linkFarm,
  writeText,
  writeShellScript,
  imageBuilder,
  systemTestsSrc,
  images,
  lock,
  ddtraceVersion ? lock.defaultDdtrace,
}:
let
  inherit (imageBuilder) mkImage bridge saveImage;

  arch = stdenv.hostPlatform.go.GOARCH;
  platform =
    {
      amd64 = "linux/amd64";
      arm64 = "linux/arm64/v8";
    }
    .${arch};

  locked =
    lock.ddtrace.${ddtraceVersion} or (throw ''
      system-tests-vanilla: ddtrace ${ddtraceVersion} is not in the weblog lock; add it with
        DDTRACE_VERSION=${ddtraceVersion} nix run .#system-tests-vanilla-lock'');

  wheelhouse = linkFarm "system-tests-${lock.variant}-wheelhouse-ddtrace-${ddtraceVersion}" (
    map (f: {
      name = f.filename;
      path = fetchurl {
        inherit (f) url sha256;
        name = lib.strings.sanitizeDerivationName f.filename;
      };
    }) locked.${arch}.files
  );

  port = "8765";
  pipConf = writeText "pip.conf" ''
    [global]
    no-index = true
    find-links = http://${bridge}:${port}/
    trusted-host = ${bridge}
  '';

  path = lib.makeBinPath [
    docker-client
    python3
    bash
    coreutils
    findutils
    gnused
    gnugrep
    gawk
  ];

  pipBase = mkImage {
    name = "system-tests-${lock.variant}-base-pip";
    steps = writeShellScript "system-tests-${lock.variant}-base-pip" ''
      set -euo pipefail
      export PATH=${path}
      export HOME="$(mktemp -d)"
      docker load < ${images.${lock.baseImage}}
      cp ${pipConf} "$HOME/pip.conf"
      printf 'FROM %s\nCOPY pip.conf /etc/pip.conf\n' ${lib.escapeShellArg lock.baseImage} \
        > "$HOME/Dockerfile"
      docker buildx build --progress=plain --platform ${platform} --load \
        -t ${lib.escapeShellArg lock.baseImage} "$HOME"
      ${saveImage} ${lib.escapeShellArg lock.baseImage} "$1"
    '';
  };

  weblog = mkImage {
    name = "system-tests-weblog-${lock.variant}-ddtrace-${ddtraceVersion}";
    steps = writeShellScript "system-tests-weblog-${lock.variant}" ''
      set -euo pipefail
      export PATH=${path}
      export HOME="$(mktemp -d)"
      docker load < ${pipBase}/image.tar
      python3 -m http.server ${port} --bind ${bridge} --directory ${wheelhouse} \
        > "$HOME/wheelhouse.log" 2>&1 &

      cp -r ${systemTestsSrc} "$HOME/system-tests"
      chmod -R u+w "$HOME/system-tests"
      cd "$HOME/system-tests"
      echo "ddtrace==${ddtraceVersion}" > binaries/python-load-from-pip

      # CI=true: build.sh shows the build's log instead of keeping it in a file.
      status=0
      CI=true ./build.sh python --weblog-variant ${lock.variant} --images weblog \
        --docker-platform ${platform} || status=$?
      echo "--- wheelhouse requests"; cat "$HOME/wheelhouse.log"
      [ "$status" = 0 ] || exit "$status"
      ${saveImage} system_tests/weblog "$1"
    '';
  };
in
lib.extendDerivation true {
  inherit
    pipBase
    wheelhouse
    pipConf
    ddtraceVersion
    ;
  inherit (lock) variant;
} weblog
