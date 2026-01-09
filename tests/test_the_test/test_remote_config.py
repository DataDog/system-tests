from utils import remote_config as rc, scenarios


@scenarios.test_the_test
def test_debugger_command_none():
    expected = {
        "targets": "ewogICJzaWduYXR1cmVzIjogWwogICAgewogICAgICAia2V5aWQiOiAiMTM5ZTM5NDBlNjRiNTQ5MTcyMjA4OGQ5YTBkNzQxNjI4ZmM4MjZlMDk0NzVkMzQxYTc4MGFjZGUzYzRiODA3MCIsCiAgICAgICJzaWciOiAiNWIyNDJlMDg5MjI0ZWExMzg5MjU0ZGE4MGQxMWQ3MWM4MDNkMGMyMGE1NDg1NzgwMGE2OTM4OWRhZjJlMjQwZTcyNTQ0Mjk0MjAzZWEyZWFmMDdmZjIzNjMxMzJjOGYxYWFmZTg4MTY0MTAwNWIwYzYwNjgwM2M4MWQzMzBiMGQiCiAgICB9CiAgXSwKICAic2lnbmVkIjogewogICAgIl90eXBlIjogInRhcmdldHMiLAogICAgImN1c3RvbSI6IHsKICAgICAgIm9wYXF1ZV9iYWNrZW5kX3N0YXRlIjogImV5Sm1iMjhpT2lBaVltRnlJbjA9IgogICAgfSwKICAgICJleHBpcmVzIjogIjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwKICAgICJzcGVjX3ZlcnNpb24iOiAiMS4wIiwKICAgICJ0YXJnZXRzIjoge30sCiAgICAidmVyc2lvbiI6IDAKICB9Cn0=",
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
        "targets": "ewogICJzaWduYXR1cmVzIjogWwogICAgewogICAgICAia2V5aWQiOiAiMTM5ZTM5NDBlNjRiNTQ5MTcyMjA4OGQ5YTBkNzQxNjI4ZmM4MjZlMDk0NzVkMzQxYTc4MGFjZGUzYzRiODA3MCIsCiAgICAgICJzaWciOiAiZjk0NzliYTAyNDRkYjBlMDAxNjdiZjczNTE0NTQxMWZmOTk3MmU2NWI0Njc5NzllODZjNDRiZmNhZmQ2OGEyNjQ4YzcyOGVkMDEwOTZhNDg4YmQ3ZWJjYTMyZTUzMWNjODdiYjBkYWYxMDA2YWQxODRjNTQ4OTQyN2Q5Nzc4MDMiCiAgICB9CiAgXSwKICAic2lnbmVkIjogewogICAgIl90eXBlIjogInRhcmdldHMiLAogICAgImN1c3RvbSI6IHsKICAgICAgIm9wYXF1ZV9iYWNrZW5kX3N0YXRlIjogImV5Sm1iMjhpT2lBaVltRnlJbjA9IgogICAgfSwKICAgICJleHBpcmVzIjogIjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwKICAgICJzcGVjX3ZlcnNpb24iOiAiMS4wIiwKICAgICJ0YXJnZXRzIjogewogICAgICAiZGF0YWRvZy8yL0xJVkVfREVCVUdHSU5HL2xvZ1Byb2JlX2xvZzE3MGFhLWFjZGEtNDQ1My05MTExLTE0NzhhNm1ldGhvZC9jb25maWciOiB7CiAgICAgICAgImN1c3RvbSI6IHsKICAgICAgICAgICJ2IjogMQogICAgICAgIH0sCiAgICAgICAgImhhc2hlcyI6IHsKICAgICAgICAgICJzaGEyNTYiOiAiZWNmMzQ3ZmIwZWE0NjE2ZmU1NTc2YzIyODNhYWY1NmUyNjFmYmNjZDMxNjJiYTIxZjNjZmQwNDJjM2VjOWFjNSIKICAgICAgICB9LAogICAgICAgICJsZW5ndGgiOiAyODkKICAgICAgfQogICAgfSwKICAgICJ2ZXJzaW9uIjogMQogIH0KfQ==",
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
