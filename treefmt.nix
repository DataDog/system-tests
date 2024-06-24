# treefmt.nix
{pkgs, ...}: {
  # Used to find the project root
  projectRootFile = "flake.nix";
  # Enable the Nix formatter "alejandra"
  programs.alejandra.enable = true;
  # Format py sources
  programs.black.enable = true;
  # Format .sh scripts
  programs.shfmt.enable = true;
  programs.shfmt.indent_size = null; # read indend from editoconfig

  # Format Markdown
  programs.mdformat.enable = true;

  settings.global.excludes = ["tests/fuzzer/**" "tests/appsec/waf/blocked*" "utils/parametric/protos/*.py" "lib-injection/common/templates/*"];
}
