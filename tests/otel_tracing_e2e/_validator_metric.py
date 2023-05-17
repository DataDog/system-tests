# Util functions to validate JSON metrics from OTel system tests

import dictdiffer

# Validates the JSON logs from backend and returns the OTel log trace attributes
def validate_metrics(metrics_agent: list[dict], metrics_collector: list[dict]):
    diff = list(dictdiffer.diff(metrics_agent[0], metrics_collector[0]))
    assert len(diff) == 0, f"Diff between count metrics from Agent vs. from Collector: {diff}"
    validate_example_counter(metrics_agent[0])
    idx = 1
    for histogram_suffix in ["", ".sum", ".count"]:
        diff = list(dictdiffer.diff(metrics_agent[idx], metrics_collector[idx]))
        assert len(diff) == 0, f"Diff between histogram{histogram_suffix} metrics from Agent vs. from Collector: {diff}"
        validate_example_histogram(metrics_agent[idx], histogram_suffix)
        idx += 1


def validate_example_counter(counter_metric: dict):
    assert len(counter_metric["series"]) == 1
    counter_series = counter_metric["series"][0]
    assert counter_series["metric"] == "example.counter"
    assert counter_series["display_name"] == "example.counter"
    assert len(counter_series["pointlist"]) == 1
    assert counter_series["pointlist"][0][1] == 11.0


def validate_example_histogram(histogram_metric: dict, histogram_suffix: str):
    assert len(histogram_metric["series"]) == 1
    histogram_series = histogram_metric["series"][0]
    assert histogram_series["metric"] == "example.histogram" + histogram_suffix
    assert histogram_series["display_name"] == "example.histogram" + histogram_suffix
    assert len(histogram_series["pointlist"]) == 1
    assert histogram_series["pointlist"][0][1] == 33.0 if histogram_suffix != ".count" else 1.0
