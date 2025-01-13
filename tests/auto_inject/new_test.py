import requests
from utils import scenarios, features
#from utils._context._scenarios.auto_injection import _VirtualMachineScenario

#new_auto_inject_scenario=new_auto_inject_scenario("MY_CUSTOM_SCENARIO","A very simple example")



        
@scenarios.new_auto_inject_scenario
class TestNewAutoInjectScenario():
    def test_whatever(self, vm):
        assert self.execute_command(vm, "echo 'Hello'") == "Hello"

    def execute_command(self, virtual_machine, command) -> str:
        # Env for the command
        prefix_env = ""
        for key, value in virtual_machine.get_command_environment().items():
            prefix_env += f"export {key}={value} \n"

        command_with_env = f"{prefix_env} {command}"

        with virtual_machine.ssh_config.get_ssh_connection() as ssh:
            timeout = 120

            _, stdout, _ = ssh.exec_command(command_with_env, timeout=timeout + 5)
            stdout.channel.set_combine_stderr(True)

            # Enforce that even if we reach the 2min mark we can still have a partial output of the command
            # and thus see where it is stuck.
            Timer(timeout, self.close_channel, (stdout.channel,)).start()

            # Read the output line by line
            command_output = ""
            for line in stdout.readlines():
                if not line.startswith("export"):
                    command_output += line

            return command_output
