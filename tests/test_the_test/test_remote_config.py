from utils import remote_config as rc, scenarios


@scenarios.test_the_test
def test_debugger_command_none():
    expected = {
        "targets": "ewogICJzaWduZWQiOiB7CiAgICAiX3R5cGUiOiAidGFyZ2V0cyIsCiAgICAiY3VzdG9tIjogewogICAgICAib3BhcXVlX2JhY2tlbmRfc3RhdGUiOiAiZXlKbWIyOGlPaUFpWW1GeUluMD0iCiAgICB9LAogICAgImV4cGlyZXMiOiAiMzAwMC0wMS0wMVQwMDowMDowMFoiLAogICAgInNwZWNfdmVyc2lvbiI6ICIxLjAiLAogICAgInRhcmdldHMiOiB7fSwKICAgICJ2ZXJzaW9uIjogMAogIH0sCiAgInNpZ25hdHVyZXMiOiBbCiAgICB7CiAgICAgICJrZXlpZCI6ICJlZDc2NzJjOWEyNGFiZGE3ODg3MmVlMzJlZTcxYzdjYjFkNTIzNWU4ZGI0ZWNiZjFjYTI4YjljNTBlYjc1ZDllIiwKICAgICAgInNpZyI6ICJlMjI3OWE1NTRkNTI1MDNmNWJkNjhlMGE5OTEwYzdlOTBjOWJiODE3NDRmZTljODgyNGVhMzczN2IyNzlkOWU2OWIzY2U1ZjRiNDYzYzQwMmViZTM0OTY0ZmI3YTY5NjI1ZWIwZTkxZDNkZGJkMzkyY2M4YjMyMTAzNzNkOWIwZiIKICAgIH0KICBdCn0=",
        "target_files": [],
        "client_configs": [],
    }

    obeserved = rc.build_debugger_command(None, 0)

    assert obeserved == expected


@scenarios.test_the_test
def test_debugger_command_one_probe():
    probes = [
        {
            "language": "",
            "id": "log170aa-acda-4453-9111-1478a6method",
            "type": "LOG_PROBE",
            "where": {"typeName": "ACTUAL_TYPE_NAME", "methodName": "Pii", "sourceFile": None},
            "evaluateAt": "EXIT",
            "captureSnapshot": True,
            "capture": {"maxFieldCount": 200},
        }
    ]

    expected = {
        "targets": "ewogICJzaWduZWQiOiB7CiAgICAiX3R5cGUiOiAidGFyZ2V0cyIsCiAgICAiY3VzdG9tIjogewogICAgICAib3BhcXVlX2JhY2tlbmRfc3RhdGUiOiAiZXlKbWIyOGlPaUFpWW1GeUluMD0iCiAgICB9LAogICAgImV4cGlyZXMiOiAiMzAwMC0wMS0wMVQwMDowMDowMFoiLAogICAgInNwZWNfdmVyc2lvbiI6ICIxLjAiLAogICAgInRhcmdldHMiOiB7CiAgICAgICJkYXRhZG9nLzIvTElWRV9ERUJVR0dJTkcvbG9nUHJvYmVfbG9nMTcwYWEtYWNkYS00NDUzLTkxMTEtMTQ3OGE2bWV0aG9kL2NvbmZpZyI6IHsKICAgICAgICAiY3VzdG9tIjogewogICAgICAgICAgInYiOiAxCiAgICAgICAgfSwKICAgICAgICAiaGFzaGVzIjogewogICAgICAgICAgInNoYTI1NiI6ICJlY2YzNDdmYjBlYTQ2MTZmZTU1NzZjMjI4M2FhZjU2ZTI2MWZiY2NkMzE2MmJhMjFmM2NmZDA0MmMzZWM5YWM1IgogICAgICAgIH0sCiAgICAgICAgImxlbmd0aCI6IDI4OQogICAgICB9CiAgICB9LAogICAgInZlcnNpb24iOiAxCiAgfSwKICAic2lnbmF0dXJlcyI6IFsKICAgIHsKICAgICAgImtleWlkIjogImVkNzY3MmM5YTI0YWJkYTc4ODcyZWUzMmVlNzFjN2NiMWQ1MjM1ZThkYjRlY2JmMWNhMjhiOWM1MGViNzVkOWUiLAogICAgICAic2lnIjogImUyMjc5YTU1NGQ1MjUwM2Y1YmQ2OGUwYTk5MTBjN2U5MGM5YmI4MTc0NGZlOWM4ODI0ZWEzNzM3YjI3OWQ5ZTY5YjNjZTVmNGI0NjNjNDAyZWJlMzQ5NjRmYjdhNjk2MjVlYjBlOTFkM2RkYmQzOTJjYzhiMzIxMDM3M2Q5YjBmIgogICAgfQogIF0KfQ==",
        "target_files": [
            {
                "path": "datadog/2/LIVE_DEBUGGING/logProbe_log170aa-acda-4453-9111-1478a6method/config",
                "raw": "ewogICJsYW5ndWFnZSI6ICIiLAogICJpZCI6ICJsb2cxNzBhYS1hY2RhLTQ0NTMtOTExMS0xNDc4YTZtZXRob2QiLAogICJ0eXBlIjogIkxPR19QUk9CRSIsCiAgIndoZXJlIjogewogICAgInR5cGVOYW1lIjogIkFDVFVBTF9UWVBFX05BTUUiLAogICAgIm1ldGhvZE5hbWUiOiAiUGlpIiwKICAgICJzb3VyY2VGaWxlIjogbnVsbAogIH0sCiAgImV2YWx1YXRlQXQiOiAiRVhJVCIsCiAgImNhcHR1cmVTbmFwc2hvdCI6IHRydWUsCiAgImNhcHR1cmUiOiB7CiAgICAibWF4RmllbGRDb3VudCI6IDIwMAogIH0KfQ==",
            }
        ],
        "client_configs": ["datadog/2/LIVE_DEBUGGING/logProbe_log170aa-acda-4453-9111-1478a6method/config"],
    }

    obeserved = rc.build_debugger_command(probes, 1)

    assert obeserved == expected
