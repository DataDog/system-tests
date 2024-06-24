# Util functions to validate JSON metrics from OTel system tests

import dictdiffer


# Validates the JSON logs from backend and returns the OTel log trace attributes
def validate_metrics(
    metrics_1: list[dict],
    metrics_2: list[dict],
    metrics_source1: str,
    metrics_source2: str,
):
    diff = list(dictdiffer.diff(metrics_1[0], metrics_2[0]))
    assert len(diff) == 0, f"Diff between count metrics from {metrics_source1} vs. from {metrics_source2}: {diff}"
    validate_example_counter(metrics_1[0])
    idx = 1
    for histogram_suffix in ["", ".sum", ".count"]:
        diff = list(dictdiffer.diff(metrics_1[idx], metrics_2[idx]))
        assert (
            len(diff) == 0
        ), f"Diff between histogram{histogram_suffix} metrics from {metrics_source1} vs. from {metrics_source2}: {diff}"
        validate_example_histogram(metrics_1[idx], histogram_suffix)
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
