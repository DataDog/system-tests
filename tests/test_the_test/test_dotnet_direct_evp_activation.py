"""Guard the .NET-only activation and lifecycle for direct-EVP validation."""

from pathlib import Path

from utils import features, scenarios


@scenarios.test_the_test
@features.not_reported
def test_dotnet_direct_evp_activation_is_exposure_only_and_poc_scoped() -> None:
    manifest = Path("manifests/dotnet.yml").read_text(encoding="utf-8")

    for test_class in (
        "Test_FFE_Exposure_Egress_Agentless_Direct",
        "Test_FFE_Exposure_Egress_Agentless_Direct_Shutdown",
        "Test_FFE_Exposure_Egress_Agentless_Sidecar",
    ):
        declaration = (
            f"tests/ffe/test_exposure_egress.py::{test_class}:\n"
            '    - weblog_declaration:\n        "*": irrelevant\n        poc: v3.54.0'
        )
        assert declaration in manifest

    assert "tests/ffe/test_flag_eval_evp.py: missing_feature (FFL-2446)" in manifest


@scenarios.test_the_test
@features.not_reported
def test_dotnet_direct_evp_shutdown_execs_runtime_and_marks_server_closed() -> None:
    app_script = Path("utils/build/docker/dotnet/weblog/app.sh").read_text(encoding="utf-8")
    program = Path("utils/build/docker/dotnet/weblog/Program.cs").read_text(encoding="utf-8")

    shutdown_switch = 'SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED:-}" = "true"'
    assert shutdown_switch in app_script
    assert "exec dotnet app.dll" in app_script
    assert app_script.index(shutdown_switch) < app_script.index("exec dotnet app.dll")
    assert app_script.index("exec dotnet app.dll") < app_script.index("if ( ! dotnet app.dll)")

    assert 'GetEnvironmentVariable("SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED") == "true"' in program
    assert "GetRequiredService<IHostApplicationLifetime>().ApplicationStopped.Register" in program
    assert 'event = "system_tests.ffe.shutdown.server_closed"' in program
    assert 'timestamp = DateTimeOffset.UtcNow.ToString("O")' in program
    assert "Console.Out.Flush();" in program
    assert program.index("ApplicationStopped.Register") < program.index("host.Run();")
