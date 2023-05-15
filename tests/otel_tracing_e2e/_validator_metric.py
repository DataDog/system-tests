# Util functions to validate JSON metrics from OTel system tests

import dictdiffer

# Validates the JSON logs from backend and returns the OTel log trace attributes
def validate_metrics(metrics_agent: list[dict], metrics_collector: list[dict]):
    diff1 = list(dictdiffer.diff(metrics_agent[0], metrics_collector[0]))
    assert len(diff1) == 0, f"Diff between count metrics from Agent vs. from Collector: {diff1}"
    validate_example_counter(metrics_agent[0])
    diff2 = list(dictdiffer.diff(metrics_agent[1], metrics_collector[1]))
    assert len(diff2) == 0, f"Diff between histogram metrics from Agent vs. from Collector: {diff2}"
    validate_example_histogram(metrics_agent[1])


def validate_example_counter(counter_metric: dict):
    assert len(counter_metric["series"]) == 1
    counter_series = counter_metric["series"][0]
    assert counter_series["metric"] == "example.counter"
    assert counter_series["display_name"] == "example.counter"
    assert len(counter_series["pointlist"]) == 1
    assert counter_series["pointlist"][0][1] == 11.0


def validate_example_histogram(histogram_metric: dict):
    assert len(histogram_metric["series"]) == 1
    histogram_series = histogram_metric["series"][0]
    assert histogram_series["metric"] == "example.histogram"
    assert histogram_series["display_name"] == "example.histogram"
    assert len(histogram_series["pointlist"]) == 1
    assert histogram_series["pointlist"][0][1] == 33.0
