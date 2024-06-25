# treefmt.nix
{
  pkgs,
  lib,
  ...
}: {
  # Used to find the project root
  projectRootFile = "flake.nix";
  # Enable the Nix formatter "alejandra"
  programs.alejandra.enable = true;
  # Format py sources
  programs.black.enable = true;
  # Format .sh scripts
  # programs.shfmt.enable = true;
  settings.global.excludes = ["tests/fuzzer/**" "tests/appsec/waf/blocked*" "utils/parametric/protos/*.py"];

  settings.formatter.whitespace = {
    command = "${pkgs.bash}/bin/bash";
    options = [
      "-euc"
      ''
        ${pkgs.gnused}/bin/sed -i -r 's/ +$//g' "$@"
      ''
      "--"
    ];
    includes = ["*.md" "*.yml" "*.yaml" "*.sh" "*.cs" "*.Dockerfile" "*.java" "*.sql" "*.ts" "*.js" "*.php"];
    excludes = ["logs*" "./manifests/*" "./utils/build/virtual_machine/*"];

    settings.global.excludes = ["./venv/*" "*/node_modules/*" "tests/appsec/waf/blocked*" "utils/parametric/protos/*.py"];
  };
}
