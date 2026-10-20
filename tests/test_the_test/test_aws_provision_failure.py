from pulumi.automation import DiagnosticEvent

from utils import features, scenarios
from utils.virtual_machine.aws_provider import _error_diagnostic_line, _provision_failure_message


@features.not_reported
@scenarios.test_the_test
class Test_AwsProvisionFailure:
    def test_remote_command_failure_names_the_step(self) -> None:
        message = (
            "command:remote:Command -Ubuntu_24_amd64-install-installer **creating failed** "
            'error: Process exited with status 1: running "echo fail && cat /var/log/huge-script"'
        )

        result = _provision_failure_message(message, "Ubuntu_24_amd64")

        assert result == (
            "Error on VM provisioning at step 'install-installer' (Process exited with status 1).\n"
            "👀 Check the log file: Ubuntu_24_amd64.log to see the full error trace.\n"
            "📝 Look for step 'install-installer' in Ubuntu_24_amd64_provision_script.log "
            "to see the source that failed."
        )

    def test_later_creating_failed_is_ignored(self) -> None:
        message = (
            "command:remote:Command -Ubuntu_24_amd64-install-installer **creating failed** "
            'error: Process exited with status 1: running "echo fail"\n'
            "command:remote:Command -Ubuntu_24_amd64-install-weblog **creating failed** error: cascade\n"
        )

        result = _provision_failure_message(message, "Ubuntu_24_amd64")

        assert "install-installer" in result
        assert "install-weblog" not in result

    def test_copy_file_failure_names_the_step_after_the_vm(self) -> None:
        message = "command:remote:CopyFile app.py-Ubuntu_24_amd64-weblog **creating failed** error: connection reset\n"

        result = _provision_failure_message(message, "Ubuntu_24_amd64")

        assert result == (
            "Error on VM provisioning at step 'weblog' (connection reset).\n"
            "👀 Check the log file: Ubuntu_24_amd64.log to see the full error trace.\n"
            "📝 Look for step 'weblog' in Ubuntu_24_amd64_provision_script.log to see the source that failed."
        )

    def test_instance_resource_is_not_a_provision_step(self) -> None:
        message = (
            "aws:ec2:Instance Ubuntu_24_amd64-cf26854c-220c-4a07-9970-d8fca34cd1fa **creating failed** "
            "error: 1 error occurred:\n"
        )

        result = _provision_failure_message(message, "Ubuntu_24_amd64")

        assert result == (
            "Error on VM provisioning (1 error occurred:).\n"
            "👀 Check the log file: Ubuntu_24_amd64.log to see the full error trace.\n"
            "📝 Look for the failed step in Ubuntu_24_amd64_provision_script.log to see the source that failed."
        )

    def test_missing_marker_mentions_only_the_log_file(self) -> None:
        result = _provision_failure_message("pulumi crashed", "Ubuntu_24_amd64")

        assert result == (
            "Error on VM provisioning.\n"
            "👀 Check the log file: Ubuntu_24_amd64.log to see the full error trace.\n"
            "📝 Look for the failed step in Ubuntu_24_amd64_provision_script.log to see the source that failed."
        )

    def test_error_diagnostic_drops_the_remote_script(self) -> None:
        diagnostic = DiagnosticEvent(
            message='Process exited with status 1: running "echo fail"',
            color="",
            severity="error",
            urn="urn:pulumi:dev::system-tests-vms::command:remote:Command::install-installer",
        )

        assert _error_diagnostic_line(diagnostic) == (
            "  command:remote:Command (install-installer):\n    error: Process exited with status 1"
        )

    def test_error_diagnostic_keeps_stderr_after_the_script(self) -> None:
        diagnostic = DiagnosticEvent(
            message='Process exited with status 1: running "echo fail"\nError simulado',
            color="",
            severity="error",
            urn="urn:pulumi:dev::system-tests-vms::command:remote:Command::install-installer",
        )

        assert _error_diagnostic_line(diagnostic) == (
            "  command:remote:Command (install-installer):\n    error: Process exited with status 1: Error simulado"
        )

    def test_non_error_and_ephemeral_diagnostics_are_ignored(self) -> None:
        warning = DiagnosticEvent(message="retrying", color="", severity="warning")
        ephemeral = DiagnosticEvent(message="dial failed", color="", severity="error", ephemeral=True)

        assert _error_diagnostic_line(warning) is None
        assert _error_diagnostic_line(ephemeral) is None
