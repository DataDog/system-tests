from utils import remote_config as rc, scenarios


@scenarios.test_the_test
def test_debugger_command_none():
    expected = {
        "targets": "eyJzaWduZWQiOiB7Il90eXBlIjogInRhcmdldHMiLCAiY3VzdG9tIjogeyJvcGFxdWVfYmFja2VuZF9zdGF0ZSI6ICJleUptYjI4aU9pQWlZbUZ5SW4wPSJ9LCAiZXhwaXJlcyI6ICIzMDAwLTAxLTAxVDAwOjAwOjAwWiIsICJzcGVjX3ZlcnNpb24iOiAiMS4wIiwgInRhcmdldHMiOiB7fSwgInZlcnNpb24iOiAwfSwgInNpZ25hdHVyZXMiOiBbeyJrZXlpZCI6ICJlZDc2NzJjOWEyNGFiZGE3ODg3MmVlMzJlZTcxYzdjYjFkNTIzNWU4ZGI0ZWNiZjFjYTI4YjljNTBlYjc1ZDllIiwgInNpZyI6ICJlMjI3OWE1NTRkNTI1MDNmNWJkNjhlMGE5OTEwYzdlOTBjOWJiODE3NDRmZTljODgyNGVhMzczN2IyNzlkOWU2OWIzY2U1ZjRiNDYzYzQwMmViZTM0OTY0ZmI3YTY5NjI1ZWIwZTkxZDNkZGJkMzkyY2M4YjMyMTAzNzNkOWIwZiJ9XX0=",
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
            "where": {"typeName": "ACTUAL_TYPE_NAME", "methodName": "Pii", "sourceFile": None},
            "evaluateAt": "EXIT",
            "captureSnapshot": True,
            "capture": {"maxFieldCount": 200},
        }
    ]

    expected = {
        "targets": "eyJzaWduZWQiOiB7Il90eXBlIjogInRhcmdldHMiLCAiY3VzdG9tIjogeyJvcGFxdWVfYmFja2VuZF9zdGF0ZSI6ICJleUptYjI4aU9pQWlZbUZ5SW4wPSJ9LCAiZXhwaXJlcyI6ICIzMDAwLTAxLTAxVDAwOjAwOjAwWiIsICJzcGVjX3ZlcnNpb24iOiAiMS4wIiwgInRhcmdldHMiOiB7ImRhdGFkb2cvMi9MSVZFX0RFQlVHR0lORy9sb2dQcm9iZV9sb2cxNzBhYS1hY2RhLTQ0NTMtOTExMS0xNDc4YTZtZXRob2QvY29uZmlnIjogeyJjdXN0b20iOiB7InYiOiAxfSwgImhhc2hlcyI6IHsic2hhMjU2IjogImY5N2FjNjJiNjU0NWU0ZDYwOTU1ZTBjNGEyMTUzODQwNTg0MjVmNzQzMTM3ODNjOTIzYWFlYjVkNzkxMzE5YTcifSwgImxlbmd0aCI6IDIzNH19LCAidmVyc2lvbiI6IDF9LCAic2lnbmF0dXJlcyI6IFt7ImtleWlkIjogImVkNzY3MmM5YTI0YWJkYTc4ODcyZWUzMmVlNzFjN2NiMWQ1MjM1ZThkYjRlY2JmMWNhMjhiOWM1MGViNzVkOWUiLCAic2lnIjogImUyMjc5YTU1NGQ1MjUwM2Y1YmQ2OGUwYTk5MTBjN2U5MGM5YmI4MTc0NGZlOWM4ODI0ZWEzNzM3YjI3OWQ5ZTY5YjNjZTVmNGI0NjNjNDAyZWJlMzQ5NjRmYjdhNjk2MjVlYjBlOTFkM2RkYmQzOTJjYzhiMzIxMDM3M2Q5YjBmIn1dfQ==",
        "target_files": [
            {
                "path": "datadog/2/LIVE_DEBUGGING/logProbe_log170aa-acda-4453-9111-1478a6method/config",
                "raw": "eyJsYW5ndWFnZSI6ICJqYXZhIiwgImlkIjogImxvZzE3MGFhLWFjZGEtNDQ1My05MTExLTE0NzhhNm1ldGhvZCIsICJ3aGVyZSI6IHsidHlwZU5hbWUiOiAiRGVidWdnZXJDb250cm9sbGVyIiwgIm1ldGhvZE5hbWUiOiAicGlpIiwgInNvdXJjZUZpbGUiOiBudWxsfSwgImV2YWx1YXRlQXQiOiAiRVhJVCIsICJjYXB0dXJlU25hcHNob3QiOiB0cnVlLCAiY2FwdHVyZSI6IHsibWF4RmllbGRDb3VudCI6IDIwMH19",
            }
        ],
        "client_configs": ["datadog/2/LIVE_DEBUGGING/logProbe_log170aa-acda-4453-9111-1478a6method/config"],
    }

    obeserved = rc.build_debugger_command(probes, 1)

    assert obeserved == expected
