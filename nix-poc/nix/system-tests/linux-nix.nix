# `linux-nix`: builds this flake's Linux attributes from macOS with Nix running in a pinned
# nixos/nix container on the Docker daemon the docker CLI points at, so no Linux builder is needed.
# The flake and its inputs are sent to the container as this build sees them, so `--override-input`
# carries over. The container's store and Nix caches (including the git clones of the inputs
# fetched during evaluation) are kept in a Docker volume, so later builds only fetch and rebuild
# what changed.
#
# Builds can use the Docker daemon (the `docker` system feature, for scenario results: see
# ./result.nix), its socket mounted in the container. They run as root, like the rest of the
# container (no build users: they could not use the socket), unsandboxed. LINUX_NIX_MAX_JOBS sets max-jobs (default:
# auto), e.g. to bound how many scenarios run at once. When the daemon's machine has /dev/kvm
# (colima with nested virtualization), the container gets it and offers the `kvm` feature too
# (vmTools.runInLinuxVM builds: ../system-tests-vanilla/weblog.nix).
#
# The container's root filesystem is read-only, as a sandbox's is to its builds: an unsandboxed
# build that writes to its $HOME (/homeless-shelter) would otherwise create it, and Nix then
# refuses every later build ("home directory /homeless-shelter exists"). Such a build fails
# instead, as it would in a sandbox. What is written goes to the volume (the store, the flake
# inputs, the build directories) or to tmpfs (/tmp, /root, /etc/system-tests).
#
#   linux-nix build <attr>           build legacyPackages.<linux system>.<attr>, print its store path
#   linux-nix exec <command>...      run a command in a container on the store volume (e.g. to
#                                    stream an image or copy a store path out)
{
  lib,
  stdenv,
  writeShellApplication,
  dockerTools,
  docker-client,
  coreutils,
  gnutar,
  flakeSources,
}:
let
  linuxSystem = "${stdenv.hostPlatform.parsed.cpu.name}-linux";

  # docker info's Architecture for linuxSystem.
  dockerArch =
    {
      aarch64-linux = "aarch64";
      x86_64-linux = "x86_64";
    }
    .${linuxSystem};

  nixImage = dockerTools.pullImage {
    imageName = "nixos/nix";
    imageDigest = "sha256:1d59121e0c361076b4f23c158d236702f2f045b3b477b51075b81ceb6188d34a";
    finalImageTag = "2.34.1";
    os = "linux";
    arch = stdenv.hostPlatform.go.GOARCH;
    hash =
      {
        aarch64-linux = "sha256-lfyHnjZqDWqdCGEd8fQye19Ge2h+UFI+bA28Jfx+GwA=";
        x86_64-linux = "sha256-jMz/Iu580qV/XcTPKqZXMUqIxNhUVI7oQ+iSl+vgnbo=";
      }
      .${linuxSystem};
  };

  # The volume holds the store of the image it was first populated from, so it is named after it.
  # Nix's caches (git clones of fetchGit inputs, the fetcher cache) are kept in it too
  # (XDG_CACHE_HOME), next to the store paths they point at, so evaluation does not refetch them.
  storeVolume = "dd-trace-ops-nix-${builtins.substring 0 12 (baseNameOf nixImage)}";
in
writeShellApplication {
  name = "linux-nix";
  runtimeInputs = [
    docker-client
    coreutils
    gnutar
  ];
  passthru = { inherit linuxSystem storeVolume nixImage; };
  text = ''
    arch="$(docker info --format '{{.Architecture}}')"
    if [ "$arch" != ${dockerArch} ]; then
      echo "the Docker daemon runs $arch, linux-nix builds for ${dockerArch}" >&2
      exit 1
    fi
    docker image inspect nixos/nix:2.34.1 >/dev/null 2>&1 || docker load < ${nixImage} >&2

    # KVM, when the daemon's machine has it (colima with nested virtualization), for the builds
    # that need the `kvm` feature (vmTools.runInLinuxVM).
    kvm=() kvm_feature=
    if docker run --rm --device /dev/kvm nixos/nix:2.34.1 true >/dev/null 2>&1; then
      kvm=(--device /dev/kvm) kvm_feature=" kvm"
    fi

    nix_config="$(printf '%s\n' \
      'experimental-features = nix-command flakes ca-derivations' \
      "max-jobs = ''${LINUX_NIX_MAX_JOBS:-auto}" 'keep-going = true' 'sandbox = false' \
      'filter-syscalls = false' "system-features = benchmark big-parallel docker$kvm_feature" \
      'build-users-group =' 'build-dir = /nix/var/linux-nix/builds')"

    case "''${1:-}" in
      build)
        shift
        attr="$1"

        # The flake and its inputs as this build sees them, so overridden inputs carry over.
        inputs="$(mktemp -d)"
        trap 'rm -rf "$inputs"' EXIT
        ${lib.concatStrings (
          lib.mapAttrsToList (name: path: ''
            ln -s ${path} "$inputs/${name}"
          '') flakeSources
        )}
        echo "building $attr for ${linuxSystem} in a nixos/nix container" >&2
        status=0
        tar -C "$inputs" -ch . \
          | docker run -i --rm -v ${storeVolume}:/nix "''${kvm[@]}" \
              -v /var/run/docker.sock:/var/run/docker.sock \
              --read-only --tmpfs /tmp --tmpfs /root --tmpfs /etc/system-tests \
              -e XDG_CACHE_HOME=/nix/var/cache -e NIX_CONFIG="$nix_config" \
              nixos/nix:2.34.1 sh -c '
                set -e
                # For scenario results (../result.nix): the daemon sees this store in the volume.
                echo ${storeVolume} > /etc/system-tests/store-volume
                mkdir -p /nix/var/linux-nix/builds
                # On the volume rather than in memory; each build its own, for concurrent builds.
                inputs="$(mktemp -d /nix/var/linux-nix/inputs.XXXXXX)"
                trap "rm -rf $inputs" EXIT
                tar -x -C "$inputs"
                nix build --print-build-logs --print-out-paths --no-link \
                  "path:$inputs/self#legacyPackages.${linuxSystem}.'"$attr"'" \
                  ${lib.concatMapStrings (name: "--override-input ${name} path:$inputs/${name} ") (
                    lib.attrNames (removeAttrs flakeSources [ "self" ])
                  )}
              ' || status=$?
        if [ "$status" = 137 ]; then
          memory="$(docker info --format '{{.MemTotal}}')"
          echo "the build container was killed, most likely out of memory: the Docker daemon has" \
            "$((memory / 1024 / 1024)) MiB (e.g. colima start --memory 8)" >&2
        fi
        exit "$status"
        ;;
      exec)
        shift
        exec docker run -i --rm -v ${storeVolume}:/nix nixos/nix:2.34.1 "$@"
        ;;
      *)
        echo "usage: linux-nix build <attr> | linux-nix exec <command>..." >&2
        exit 2
        ;;
    esac
  '';
}
