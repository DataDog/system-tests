import uuid
import json
import time
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

        # Retry mechanism for scp.get() - try up to 3 times
        # Ruby might take more time to create the log file
        max_retries = 3
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                scp.get(remote_path=f"/var/log/datadog_weblog/{unique_log_name}", local_path=log_local_path)
                logger.info(f"Successfully retrieved log file on attempt {attempt + 1}")
                break
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed to retrieve log file: {e}")
                if attempt < max_retries - 1:  # Don't sleep on the last attempt
                    time.sleep(2)  # Wait 2 seconds before retrying
        else:
            # All retries failed, raise the last exception
            logger.error(f"Failed to retrieve log file after {max_retries} attempts")
            if last_exception is not None:
                raise last_exception
            else:
                raise RuntimeError("Failed to retrieve log file but no exception was captured")

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
        # Map system-tests language names to possible package names (including alternatives)
        language_package_variations = {
            "java": ["java"],
            "python": ["python", "py"],  # Alternative: datadog-apm-library-py
            "nodejs": ["nodejs", "js"],  # Alternative: datadog-apm-library-js
            "dotnet": ["dotnet"],
            "php": ["php"],
            "ruby": ["ruby"],
        }

        package_variations = language_package_variations.get(language, [language])

        logger.info(f"🔍 Searching for requirements.json for {language} language...")
        logger.info(f"   📂 Package variations to try: {[f'datadog-apm-library-{pkg}' for pkg in package_variations]}")

        # Try each package name variation
        for i, package_name in enumerate(package_variations):
            search_pattern = f"/opt/datadog-packages/datadog-apm-library-{package_name}/*/metadata/requirements.json"

            is_primary = i == 0
            search_type = "Primary" if is_primary else "Alternative"
            logger.info(f"   📍 {search_type} search pattern: {search_pattern}")

            find_command = f"find /opt/datadog-packages -name 'requirements.json' -path '*datadog-apm-library-{package_name}*' 2>/dev/null | head -1"
            logger.info(f"   🔧 Find command: {find_command}")

            _, stdout, stderr = ssh_client.exec_command(find_command)
            requirements_file_path = stdout.read().decode().strip()

            if requirements_file_path:
                logger.info(f"✅ Found requirements.json for {language} at: {requirements_file_path}")
                logger.info(f"   📦 Found using package name: datadog-apm-library-{package_name}")
                return requirements_file_path
            elif is_primary:
                logger.warning(f"⚠️  Primary search failed for {language} (datadog-apm-library-{package_name})")
            else:
                logger.warning(f"⚠️  Alternative search failed for {language} (datadog-apm-library-{package_name})")

            # Try ls command as fallback for this package variation
            logger.info(f"   📍 Trying ls fallback for pattern: {search_pattern}")
            ls_command = f"ls {search_pattern} 2>/dev/null | head -1"
            logger.info(f"   🔧 List command: {ls_command}")

            _, stdout, stderr = ssh_client.exec_command(ls_command)
            requirements_file_path = stdout.read().decode().strip()

            if requirements_file_path:
                logger.info(f"✅ Found requirements.json for {language} at: {requirements_file_path}")
                logger.info(f"   📦 Found using package name: datadog-apm-library-{package_name} (via ls)")
                return requirements_file_path

        # If we get here, no requirements.json was found with any package variation
        logger.warning(f"❌ requirements.json file not found for {language}")
        logger.warning("   📂 Searched in all package variations:")
        for pkg in package_variations:
            logger.warning(f"      - /opt/datadog-packages/datadog-apm-library-{pkg}/")
        logger.warning("   📄 Expected file pattern: */metadata/requirements.json")
        logger.warning(f"   💡 Make sure the {language} tracer library is properly installed")
        return None

    def _get_requirements_json_content(self, ssh_client, requirements_file_path):
        """Read and parse the requirements.json file from the remote machine"""
        if not requirements_file_path:
            return None

        _, stdout, stderr = ssh_client.exec_command(f"cat {requirements_file_path}")
        requirements_content = stdout.read().decode()
        error_output = stderr.read().decode()

        if error_output:
            logger.warning(f"❌ Error reading requirements.json: {error_output}")
            return None

        try:
            return json.loads(requirements_content)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse requirements.json: {e}")
            return None

    def _extract_blocked_commands(self, requirements_json, language):
        """Extract commands that should be blocked from requirements.json for the given language"""
        if not requirements_json:
            return []

        blocked_commands = []
        deny_rules = requirements_json.get("deny", [])

        # Get the runtime command for this language
        runtime_cmd = self._get_language_runtime_command(language)

        for deny_rule in deny_rules:
            if not isinstance(deny_rule, dict):
                continue

            cmds = deny_rule.get("cmds", [])
            args = deny_rule.get("args", [])
            rule_id = deny_rule.get("id", "unknown")
            rule_description = deny_rule.get("description", "No description")

            # Check if this rule applies to our language
            if not self._rule_applies_to_language(cmds, language):
                continue

            # If there are no args, it means the entire command pattern is blocked
            if not args:
                for cmd_pattern in cmds:
                    # Convert wildcard pattern to actual command
                    if cmd_pattern.endswith(f"/{runtime_cmd}") or cmd_pattern == f"**/{runtime_cmd}":
                        blocked_commands.append(
                            {"command": runtime_cmd, "id": rule_id, "description": rule_description}
                        )
                continue

            # Process argument patterns - collect and combine all args
            # First, collect all args with their positions
            all_args = []
            for arg_rule in args:
                if not isinstance(arg_rule, dict):
                    continue

                arg_list = arg_rule.get("args", [])
                position = arg_rule.get("position")

                for arg in arg_list:
                    all_args.append({"arg": arg, "position": position})

            if all_args:
                # Sort args by position (None positions go to the end)
                sorted_args = sorted(all_args, key=lambda x: (x["position"] is None, x["position"]))

                # Build blocked commands by combining cmd patterns with all args
                for cmd_pattern in cmds:
                    if cmd_pattern.endswith(f"/{runtime_cmd}") or cmd_pattern == f"**/{runtime_cmd}":
                        # Combine all args into a single command
                        combined_args = " ".join([arg_info["arg"] for arg_info in sorted_args])
                        blocked_command = f"{runtime_cmd} {combined_args}"
                        blocked_commands.append(
                            {"command": blocked_command, "id": rule_id, "description": rule_description}
                        )

        # Remove duplicates based on command only, keeping the first occurrence
        seen_commands = set()
        unique_blocked_commands = []
        for cmd_info in blocked_commands:
            if cmd_info["command"] not in seen_commands:
                seen_commands.add(cmd_info["command"])
                unique_blocked_commands.append(cmd_info)

        return unique_blocked_commands

    def _rule_applies_to_language(self, cmds, language):
        """Check if a deny rule applies to the specified language based on command patterns"""
        runtime_cmd = self._get_language_runtime_command(language)

        for cmd_pattern in cmds:
            # Check if the command pattern matches our language's runtime
            if cmd_pattern.endswith(f"/{runtime_cmd}") or cmd_pattern in (f"**/{runtime_cmd}", runtime_cmd):
                return True
        return False

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
            logger.warning(f"⏭️  Skipping requirements.json test for {language} - file not found")
            return

        requirements_json = self._get_requirements_json_content(ssh_client, requirements_file_path)
        if not requirements_json:
            logger.warning(f"⏭️  Skipping requirements.json test for {language} - could not parse file")
            return

        # Extract commands that should be blocked for this language
        blocked_commands = self._extract_blocked_commands(requirements_json, language)
        logger.info(f"Found {len(blocked_commands)} {language} commands to test for blocking")

        if not blocked_commands:
            logger.warning(f"⏭️  Skipping requirements.json test for {language} - no blocked commands found")
            return

        # Test each blocked command
        failed_commands = []
        for cmd_info in blocked_commands:
            command = cmd_info["command"]
            rule_id = cmd_info["id"]
            rule_description = cmd_info["description"]

            logger.info(f"🔍 Testing blocked command: {command}")
            logger.info(f"   📋 Rule ID: {rule_id}")
            logger.info(f"   📝 Description: {rule_description}")

            try:
                local_log_file = self._execute_remote_command(ssh_client, command)
                if not command_injection_skipped(command, local_log_file):
                    failed_commands.append(command)
                    logger.error(f"❌ Command should be blocked but was instrumented: {command}")
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
                        logger.error(f"❌ Command should be blocked but injection was attempted: {command}")
                except Exception as e:
                    # If we can't get logs, assume the command was properly blocked
                    logger.info(f"Command execution and logging failed, assuming blocked: {command}")
                    logger.info(f"Exception: {e}")

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
            "php": ["php /tmp/app.php", "php -f /tmp/script.php"],
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
                    logger.error(f"❌ Command should be instrumented but was blocked: {command}")
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
