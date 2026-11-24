{...}: {
  name = "ping test";

  # We're using `containers` instead of `nodes` here!
  # Nothing else changes
  containers = {
    machine1 = {};
    machine2 = {};
  };

  testScript = ''
    start_all()

    machine1.succeed("ping -c 1 machine2")
    machine2.succeed("ping -c 1 machine1")
  '';
}
