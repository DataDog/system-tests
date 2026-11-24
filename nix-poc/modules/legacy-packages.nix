# The whole ddtrace graph (see ../nix/default.nix), per system.
#
# Content addressing needs the `ca-derivations` experimental feature on the Nix daemon.
# `without-ca` builds the same graph as input-addressed derivations for daemons without it.
{ self, inputs, ... }:
{
  perSystem =
    { pkgs, inputs', ... }:
    let
      inherit (inputs) dd-trace-py system-tests;
      # lib.fileset needs a path value; the input's outPath is a store path string.
      root = /. + builtins.unsafeDiscardStringContext dd-trace-py.outPath;
      systemTestsRoot = /. + builtins.unsafeDiscardStringContext system-tests.outPath;
      ddtrace =
        contentAddressed:
        import ../nix {
          inherit pkgs contentAddressed;
          crate2nix-cli = inputs'.crate2nix.packages.default;
          inherit root systemTestsRoot;
          flakeSources = {
            self = self.outPath;
            dd-trace-py = dd-trace-py.outPath;
            system-tests = system-tests.outPath;
          };
        };
    in
    {
      legacyPackages = ddtrace true // {
        without-ca = ddtrace false;
      };
    };
}
