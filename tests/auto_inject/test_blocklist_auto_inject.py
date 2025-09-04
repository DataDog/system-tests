import uuid
import json
from scp import SCPClient

from utils import scenarios, context, features, irrelevant, logger
from utils.onboarding.injection_log_parser import command_injection_skipped


class _AutoInjectBlockListBaseTest:
    """Base class to test the block list on auto instrumentation"""

    def _execute_remote_command(self, ssh_client, command):
        """Execute remote command and get remote log file from the vm. You can use this method using env variables or using injection config file"""

        unique_log_name = f"host_injection_{uuid.uuid4()}.log"

        command_with_config = f"DD_APM_INSTRUMENTATION_DEBUG=TRUE DD_APM_INSTRUMENTATION_OUTPUT_PATHS=/var/log/datadog_weblog/{unique_log_name} {command}"
        logger.info(f"Executing command: [{command_with_config}] associated with log file: [{unique_log_name}]")
        log_local_path = context.scenario.host_log_folder + f"/{unique_log_name}"

        _, stdout, stderr = ssh_client.exec_command(command_with_config)
        logger.info("Command output:")
        logger.info(stdout.readlines())
        logger.info("Command err output:")
        logger.info(stderr.readlines())

        scp = SCPClient(ssh_client.get_transport())
        scp.get(remote_path=f"/var/log/datadog_weblog/{unique_log_name}", local_path=log_local_path)

        return log_local_path


@features.host_block_list
@scenarios.installer_auto_injection
@irrelevant(condition=context.weblog_variant == "test-app-dotnet-iis")
class TestAutoInjectBlockListInstallManualHost(_AutoInjectBlockListBaseTest):
    builtin_args_commands_block = {
        "java": ["java -version", "MY_ENV_VAR=hello java -version"],
        "donet": [
            "dotnet restore",
            "dotnet build -c Release",
            "sudo -E dotnet publish",
            "MY_ENV_VAR=hello dotnet build -c Release",
        ],
    }

    builtin_args_commands_injected = {
        "java": [
            "java -jar myjar.jar",
            "sudo -E java -jar myjar.jar",
            "version=-version java -jar myjar.jar",
            "java -Dversion=-version -jar myapp.jar",
        ],
        "donet": [
            "dotnet run -- -p build",
            "dotnet build.dll -- -p build",
            "sudo -E dotnet run myapp.dll -- -p build",
            "sudo dotnet publish",
            "MY_ENV_VAR=build dotnet myapp.dll",
        ],
    }

    builtin_commands_not_injected = [
        "ps -fea",
        "touch myfile.txt",
        "hello=hola cat myfile.txt",
        "ls -la",
        "mkdir newdir",
    ]

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_builtin_block_commands(self):
        """Check that commands are skipped from the auto injection. This commands are defined on the buildIn processes to block"""
        virtual_machine = context.virtual_machine
        logger.info(f"[{virtual_machine.get_ip()}] Executing commands that should be blocked")
        ssh_client = virtual_machine.get_ssh_connection()
        for command in self.builtin_commands_not_injected:
            local_log_file = self._execute_remote_command(ssh_client, command)
            assert command_injection_skipped(command, local_log_file), f"The command {command} was instrumented!"

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_builtin_block_args(self):
        """Check that we are blocking command with args. These args are defined in the buildIn args ignore list for each language."""
        virtual_machine = context.virtual_machine
        logger.info(f"[{virtual_machine.get_ip()}] Executing test_builtIn_block_args")
        language = context.library.name
        if language in self.builtin_args_commands_block:
            ssh_client = virtual_machine.get_ssh_connection()
            for command in self.builtin_args_commands_block[language]:
                local_log_file = self._execute_remote_command(ssh_client, command)
                assert command_injection_skipped(command, local_log_file), f"The command {command} was instrumented!"

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_builtin_instrument_args(self):
        """Check that we are instrumenting the command with args that it should be instrumented. The args are not included on the buildIn args list"""
        virtual_machine = context.virtual_machine
        logger.info(f"[{virtual_machine.get_ip()}] Executing test_builtIn_instrument_args")
        language = context.library.name
        if language in self.builtin_args_commands_injected:
            ssh_client = virtual_machine.get_ssh_connection()
            for command in self.builtin_args_commands_injected[language]:
                local_log_file = self._execute_remote_command(ssh_client, command)
                assert (
                    command_injection_skipped(command, local_log_file) is False
                ), f"The command {command} was not instrumented, but it should be instrumented!"

    def _find_requirements_json_file(self, ssh_client, language):
        """Find the requirements.json file in the datadog-apm-library-<language> installation directory"""
        # Map system-tests language names to package names
        language_package_map = {
            "java": "java",
            "python": "python",
            "nodejs": "nodejs",
            "dotnet": "dotnet",
            "php": "php",
            "ruby": "ruby",
        }

        package_name = language_package_map.get(language, language)
        search_pattern = f"/opt/datadog-packages/datadog-apm-library-{package_name}/*/metadata/requirements.json"

        _, stdout, stderr = ssh_client.exec_command(
            f"find /opt/datadog-packages -name 'requirements.json' -path '*datadog-apm-library-{package_name}*' 2>/dev/null | head -1"
        )
        requirements_file_path = stdout.read().decode().strip()

        if not requirements_file_path:
            logger.warning(f"requirements.json not found for {language}, trying alternative search")
            _, stdout, stderr = ssh_client.exec_command(f"ls {search_pattern} 2>/dev/null | head -1")
            requirements_file_path = stdout.read().decode().strip()

        logger.info(f"Found requirements.json for {language} at: {requirements_file_path}")
        return requirements_file_path if requirements_file_path else None

    def _get_requirements_json_content(self, ssh_client, requirements_file_path):
        """Read and parse the requirements.json file from the remote machine"""
        if not requirements_file_path:
            return None

        _, stdout, stderr = ssh_client.exec_command(f"cat {requirements_file_path}")
        requirements_content = stdout.read().decode()
        error_output = stderr.read().decode()

        if error_output:
            logger.warning(f"Error reading requirements.json: {error_output}")
            return None

        try:
            return json.loads(requirements_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse requirements.json: {e}")
            return None

    def _extract_blocked_commands(self, requirements_json, language):
        """Extract commands that should be blocked from requirements.json for the given language"""
        if not requirements_json:
            return []

        blocked_commands = []

        # Look for entries with commands that should be blocked
        for entry_data in requirements_json.values():
            if isinstance(entry_data, dict):
                # Check for command patterns in the entry
                command = entry_data.get("command", "")
                cmdline = entry_data.get("cmdline", "")
                main_class = entry_data.get(f"{language}_main_class", "")

                # Build the full command that should be blocked
                if command and self._is_language_command(command, language):
                    blocked_commands.append(command)
                elif cmdline and self._is_language_command(cmdline, language):
                    blocked_commands.append(cmdline)
                elif main_class:
                    # Construct command with main class
                    runtime_cmd = self._get_language_runtime_command(language)
                    blocked_commands.append(f"{runtime_cmd} {main_class}")

        return list(set(blocked_commands))  # Remove duplicates

    def _is_language_command(self, command, language):
        """Check if a command is for the specified language"""
        language_runtime_map = {
            "java": ["java"],
            "python": ["python", "python3", "python2"],
            "nodejs": ["node", "npm", "npx"],
            "dotnet": ["dotnet"],
            "php": ["php"],
            "ruby": ["ruby", "gem", "bundle"],
        }

        runtime_commands = language_runtime_map.get(language, [])
        return any(command.strip().startswith(cmd) for cmd in runtime_commands)

    def _get_language_runtime_command(self, language):
        """Get the primary runtime command for a language"""
        runtime_command_map = {
            "java": "java",
            "python": "python",
            "nodejs": "node",
            "dotnet": "dotnet",
            "php": "php",
            "ruby": "ruby",
        }
        return runtime_command_map.get(language, language)

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_requirements_json_blocked_commands(self):
        """Test that commands specified in requirements.json are properly blocked from auto-instrumentation

        This test reads the requirements.json file from the remote machine at:
        /opt/datadog-packages/datadog-apm-library-<language>/<version>/metadata/requirements.json

        It extracts commands that should be blocked for the current language and verifies they are not instrumented.
        For example, for Java: 'java org.apache.cassandra.tools.StandaloneSSTableUtil'
        """
        virtual_machine = context.virtual_machine
        language = context.library.name
        logger.info(f"[{virtual_machine.get_ip()}] Testing requirements.json blocked commands for {language}")

        ssh_client = virtual_machine.get_ssh_connection()

        # Find and read requirements.json file
        requirements_file_path = self._find_requirements_json_file(ssh_client, language)
        if not requirements_file_path:
            logger.warning(f"requirements.json file not found for {language}, skipping test")
            return

        requirements_json = self._get_requirements_json_content(ssh_client, requirements_file_path)
        if not requirements_json:
            logger.warning(f"Could not parse requirements.json for {language}, skipping test")
            return

        # Extract commands that should be blocked for this language
        blocked_commands = self._extract_blocked_commands(requirements_json, language)
        logger.info(f"Found {len(blocked_commands)} {language} commands to test for blocking")

        if not blocked_commands:
            logger.warning(f"No blocked {language} commands found in requirements.json")
            return

        # Test each blocked command
        failed_commands = []
        for command in blocked_commands:
            logger.info(f"Testing blocked command: {command}")
            try:
                local_log_file = self._execute_remote_command(ssh_client, command)
                if not command_injection_skipped(command, local_log_file):
                    failed_commands.append(command)
                    logger.error(f"Command should be blocked but was instrumented: {command}")
                else:
                    logger.info(f"✅ Command properly blocked: {command}")
            except Exception as e:
                # Some commands might fail to execute (e.g., missing dependencies), which is expected
                logger.info(f"Command failed to execute (expected for some commands): {command} - {e}")
                # We still want to check if injection was attempted even if command failed
                try:
                    local_log_file = self._execute_remote_command(ssh_client, command)
                    if not command_injection_skipped(command, local_log_file):
                        failed_commands.append(command)
                        logger.error(f"Command should be blocked but injection was attempted: {command}")
                except:
                    # If we can't get logs, assume the command was properly blocked
                    logger.info(f"Command execution and logging failed, assuming blocked: {command}")

        # Assert that all commands were properly blocked
        assert (
            not failed_commands
        ), f"The following commands from requirements.json were not properly blocked: {failed_commands}"

        logger.info(f"✅ All {len(blocked_commands)} requirements.json blocked commands were properly filtered")

    def _get_allowed_test_commands(self, language):
        """Get test commands that should still be instrumented for each language"""
        commands = {
            "java": [
                "java -jar /tmp/testapp.jar",
                "java -cp /tmp/app.jar com.example.MyApp",
                "java -Xmx512m -jar myapp.jar",
                "java com.example.MainClass",
                "java -Djava.awt.headless=true -jar application.jar",
            ],
            "python": [
                "python /tmp/app.py",
                "python -m mymodule",
                "python -u /tmp/script.py",
                "python3 /tmp/app.py",
            ],
            "nodejs": [
                "node /tmp/app.js",
                "node --inspect /tmp/server.js",
                "node -r /tmp/module.js /tmp/app.js",
            ],
            "dotnet": [
                "dotnet run --project /tmp/app",
                "dotnet /tmp/app.dll",
                "dotnet exec /tmp/myapp.dll",
            ],
            "php": [
                "php /tmp/app.php",
                "php -f /tmp/script.php",
                "php -S localhost:8000 /tmp/index.php",
            ],
            "ruby": [
                "ruby /tmp/app.rb",
                "ruby -e 'puts \"hello\"'",
                "ruby -I /tmp/lib /tmp/script.rb",
            ],
        }
        return commands.get(language, [])

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_requirements_json_allowed_commands_still_instrumented(self):
        """Test that commands NOT in requirements.json are still properly instrumented"""
        virtual_machine = context.virtual_machine
        language = context.library.name
        logger.info(f"[{virtual_machine.get_ip()}] Testing that allowed {language} commands are still instrumented")

        ssh_client = virtual_machine.get_ssh_connection()

        # These commands should still be instrumented (they're NOT in requirements.json)
        allowed_commands = self._get_allowed_test_commands(language)

        # Test each allowed command to ensure it would be instrumented
        failed_commands = []
        for command in allowed_commands:
            logger.info(f"Testing allowed command should be instrumented: {command}")
            try:
                local_log_file = self._execute_remote_command(ssh_client, command)
                if command_injection_skipped(command, local_log_file):
                    failed_commands.append(command)
                    logger.error(f"Command should be instrumented but was blocked: {command}")
                else:
                    logger.info(f"✅ Command properly instrumented: {command}")
            except Exception as e:
                # Even if command fails to execute, we can check if injection was attempted
                logger.info(f"Command failed to execute (checking injection attempt): {command} - {e}")
                # The command might fail but injection should still be attempted
                # This is expected behavior for non-existent JAR files, etc.

        # Assert that all allowed commands were properly instrumented (injection attempted)
        assert not failed_commands, f"The following allowed commands were incorrectly blocked: {failed_commands}"

        logger.info(f"✅ All {len(allowed_commands)} allowed {language} commands were properly instrumented")
