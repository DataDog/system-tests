{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    (flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };

        local-registry-config = pkgs.writeTextFile {
          name = "config.yaml";
          text = builtins.toJSON {
            version = 0.1;
            storage = {
              delete = {
                enabled = true;
              };
              cache = {
                blobdescriptor = "inmemory";
              };
              filesystem = {
                rootdirectory = "\${storagePath}";
              };
            };
            http = {
              addr = ":\${port}";
            };
          };
        };
        getExe = pkgs.lib.getExe;

        local-registry = pkgs.writeShellScriptBin "local-registry" ''
          #!${pkgs.bash}/bin/bash
          set -euxo pipefail
          export storagePath=$(${getExe pkgs.mktemp} -d)
          export port=5000
          ${getExe pkgs.envsubst} -i ${local-registry-config} -o $storagePath/config.yaml
          cat $storagePath/config.yaml

          ${pkgs.docker-distribution}/bin/registry serve $storagePath/config.yaml
        '';

        injection-testing-tools = pkgs.buildEnv {
          name = "injection-testing-tools";
          paths = with pkgs; [
            crane
            skopeo
            amazon-ecr-credential-helper
            local-registry
          ];
          pathsToLink = [ "/bin" ];
          extraOutputsToInstall = [ ];
        };
      in
      {
        packages = {
          inherit injection-testing-tools;
          default = injection-testing-tools;
        };
      }
    ));
}
