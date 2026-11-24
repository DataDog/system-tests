# How images are built: one derivation per image, whose output is the only interface downstream
# code sees:
#
#   $out/image.tar    `docker save <ref>`
#   $out/image.json   { ref, id, architecture, labels }
#
# so the backend can change here without touching anything that consumes images. Neither output
# references the store: nothing the build used (daemon, BuildKit, the steps' tools) reaches a run.
#
#   mkImage { name, steps }
#
# `steps` is a script run as `steps <out dir>` against a running Docker daemon with no network,
# whose default bridge gateway is `bridge` (to serve build-time files to RUN steps). It builds the
# image and calls `save-image <ref> <out dir>`. Backends (`imageBackend`, a scope attribute):
#
#   "docker"  in a privileged docker:dind container with `--network none` and the store mounted
#             read-only, through the builder's Docker daemon (the `docker` system feature, like
#             ../system-tests/result.nix). The default.
#   "vm"      vmTools.runInLinuxVM, dockerd from nixpkgs in a KVM VM (the `kvm` feature). Works
#             under colima's nested virtualization, but I/O there is far too slow to use.
{
  lib,
  stdenv,
  vmTools,
  docker,
  docker-client,
  jq,
  coreutils,
  util-linux,
  e2fsprogs,
  runCommand,
  writeShellScript,
  dind-image,
  imageBackend ? "docker",
  # Extra qemu options of the VM backend, e.g. "-smp 1".
  vmOpts ? "",
}:
let
  bridge = "172.31.0.1";

  saveImage = writeShellScript "save-image" ''
    set -euo pipefail
    export PATH=${
      lib.makeBinPath [
        docker-client
        jq
        coreutils
      ]
    }
    ref="$1" out="$2"
    mkdir -p "$out"
    docker save "$ref" -o "$out/image.tar"
    docker image inspect "$ref" \
      | jq --arg ref "$ref" '.[0] | {ref: $ref, id: .Id, architecture: .Architecture, labels: .Config.Labels}' \
      > "$out/image.json"
    cat "$out/image.json"
  '';

  vmTools' = vmTools.override {
    rootModules = [
      "virtio_pci"
      "virtio_mmio"
      "virtio_blk"
      "virtio_balloon"
      "virtio_rng"
      "ext4"
      "virtiofs"
      "crc32c"
      "overlay"
      "bridge"
      "veth"
    ];
  };

  viaDocker =
    { name, steps }:
    let
      entrypoint = writeShellScript "${name}-dind" ''
        set -euo pipefail
        mkdir -p /work
        /usr/local/bin/dockerd-entrypoint.sh dockerd --bip ${bridge}/24 > /work/dockerd.log 2>&1 &
        for _ in $(seq 120); do /usr/local/bin/docker info > /dev/null 2>&1 && break; sleep 1; done
        ${steps} /work/out
      '';
    in
    runCommand name
      {
        nativeBuildInputs = [ docker-client ];
        requiredSystemFeatures = [ "docker" ];
        # Nothing a build uses may reach a run: images reference no store path.
        allowedReferences = [ ];
      }
      ''
        export HOME="$TMPDIR"
        docker image inspect docker:28-dind > /dev/null 2>&1 || docker load < ${dind-image} > /dev/null
        if [ -f /etc/system-tests/store-volume ]; then
          store="$(cat /etc/system-tests/store-volume):/nix:ro"
        else
          store=/nix/store:/nix/store:ro
        fi
        container="${name}-$$-$RANDOM"
        trap 'docker rm --force --volumes "$container" > /dev/null 2>&1 || true' EXIT
        docker run --privileged --network none --name "$container" -v "$store" \
          --entrypoint ${entrypoint} docker:28-dind
        docker cp "$container":/work/out "$out"
      '';

  inVM =
    { name, steps }:
    vmTools'.runInLinuxVM (
      stdenv.mkDerivation {
        inherit name;
        allowedReferences = [ ];
        memSize = 4096;
        QEMU_OPTS = vmOpts;
        # The daemon's data root: overlayfs needs a real file system, not the VM's tmpfs.
        preVM = vmTools.createEmptyImage {
          size = 16384;
          fullName = "docker-data";
          destination = "./docker-data";
        };
        buildCommand = ''
          # The serial console's \r\n makes every line blank in Nix's log.
          ${coreutils}/bin/stty -F /dev/console -onlcr || true
          export PATH=${
            lib.makeBinPath [
              docker
              coreutils
              util-linux
              e2fsprogs
            ]
          }
          mkfs.ext4 -q /dev/vda
          mkdir -p /var/lib/docker /etc/docker
          mount /dev/vda /var/lib/docker
          mount -t cgroup2 none /sys/fs/cgroup
          # The classic image store: images loaded once, not stored then unpacked again.
          echo '{"features": {"containerd-snapshotter": false}}' > /etc/docker/daemon.json
          echo "root:x:0:" > /etc/group
          dockerd --data-root /var/lib/docker --iptables=false --ip6tables=false \
            --bip ${bridge}/24 > /tmp/dockerd.log 2>&1 &
          for _ in $(seq 600); do docker info > /dev/null 2>&1 && break; sleep 1; done
          docker info > /dev/null || { cat /tmp/dockerd.log; exit 1; }
          ${steps} $out
        '';
      }
    );

  backends = {
    docker = viaDocker;
    vm = inVM;
  };
in
{
  inherit bridge saveImage backends;
  mkImage = backends.${imageBackend} or (throw "imageBackend: docker or vm, not ${imageBackend}");
}
