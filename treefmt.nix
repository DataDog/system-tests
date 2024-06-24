# treefmt.nix
{pkgs, ...}: {
  # Used to find the project root
  projectRootFile = "flake.nix";
  # Enable the Nix formatter "alejandra"
  programs.alejandra.enable = true;
  # Format py sources
  programs.black.enable = true;
  # Format .sh scripts
  # programs.beautysh.enable = true;
  # Format Markdown
  programs.mdformat.enable = true;
  # set prettier to only format markdown
  # settings.formatter.prettier.includes = ["*.md"];
  settings.global.excludes = ["tests/fuzzer/**" "tests/appsec/waf/blocked*" "utils/parametric/protos/*.py" "lib-injection/common/templates/*"];
}
