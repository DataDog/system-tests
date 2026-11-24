{
  description = "ddtrace built from source as a graph of small, content-addressed derivations";

  inputs = {
    # The dd-trace-py sources to build. Override to build a branch or a local checkout, e.g.
    #   --override-input dd-trace-py github:DataDog/dd-trace-py/<branch>
    #   --override-input dd-trace-py git+file:///path/to/dd-trace-py
    dd-trace-py = {
      url = "github:DataDog/dd-trace-py";
      flake = false;
    };
    # The system-tests checkout the weblogs are built from. Override like dd-trace-py.
    system-tests = {
      url = "github:DataDog/system-tests";
      flake = false;
    };
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    import-tree.url = "github:vic/import-tree";
    crate2nix = {
      url = "github:nix-community/crate2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  # Every .nix file under ./modules is a flake-parts module. The derivations themselves live in
  # ./nix, which is plain Nix code imported from ./modules/legacy-packages.nix.
  outputs =
    inputs: inputs.flake-parts.lib.mkFlake { inherit inputs; } (inputs.import-tree ./modules);
}
