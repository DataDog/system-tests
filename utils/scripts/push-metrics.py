# Successfully installed datadog_api_client-2.24.1

from datetime import datetime, UTC

import requests

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client.v1.model.metrics_payload import MetricsPayload
from datadog_api_client.v1.model.series import Series
from datadog_api_client.v1.model.metric_content_encoding import MetricContentEncoding
from datadog_api_client.v1.model.point import Point


def flatten(obj: dict, parent_key: str = "", sep: str = ".") -> list:
    result = []
    for k, v in obj.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            result.extend(flatten(v, new_key, sep=sep))
        elif isinstance(v, (int, float)):
            result.append((new_key, v))

    return result


def main() -> None:
    data = requests.get("https://dd-feature-parity.azurewebsites.net/statistics", timeout=10)
    values = flatten(data.json())

    series = [Series(metric=name, points=[Point([(datetime.now(UTC)).timestamp(), value])]) for name, value in values]

    configuration = Configuration(host="datad0g.com")
    with ApiClient(configuration) as api_client:
        api_instance = MetricsApi(api_client)
        response = api_instance.submit_metrics(
            content_encoding=MetricContentEncoding.DEFLATE, body=MetricsPayload(series=series)
        )

        print(response)


if __name__ == "__main__":
    main()
