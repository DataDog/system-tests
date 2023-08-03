# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from datetime import datetime, timedelta


def get_readable_integer_value(value):
    if value == 0:
        return "-"

    if value <= 9999:
        return f"{int(value)}"

    if value < 9999 * 1024:
        return f"{int(value/1024)}k"

    if value < 9999 * 1024 * 1024:
        return f"{int(value/(1024*1024))}M"

    return f"{int(value/(1024*1024*1024))}G"


class Metric:
    def __init__(
        self, name, format_string=None, display_length=5, value=0, has_raw_value=True, raw_name=None,
    ):
        self.included_in_pulse = True
        self.name = name
        self.raw_name = raw_name if raw_name else name
        self.value = value
        self.global_value = value
        self.format_string = "{value}" if format_string is None else format_string
        self.display_length = display_length
        self.has_raw_value = has_raw_value

    def update(self, value=None):
        self.value = value
        self.global_value = value

    def observe(self):
        """
        Will be called before printing
        """

    def observe_global_value(self):
        self.value = self.global_value
        self.observe()

    def reset(self):
        """
        Will be called after printing
        """

    @property
    def pretty(self):
        """
        Will be printed
        """
        return self.format_string.format(value=str(self.value))

    @property
    def raw(self):
        """
        Will be exported for later analysis
        """
        return self.value

    @property
    def is_null(self):
        """
        if true, will not reported in log file
        """
        return False


class NumericalMetric(Metric):
    @property
    def pretty(self):
        return get_readable_integer_value(self.value)


class BooleanMetric(Metric):
    @property
    def pretty(self):
        return "🚀" if self.value else "🚫"


class AccumulatedMetric(Metric):
    def update(self, value=1):
        self.value += value
        self.global_value += value

    @property
    def is_null(self):
        return self.value == 0


class ResetedAccumulatedMetric(AccumulatedMetric):
    def reset(self):
        self.value = 0

    @property
    def pretty(self):
        return get_readable_integer_value(self.value)


class RateMetric(AccumulatedMetric):
    def __init__(self, name):
        super().__init__(name)
        self.last_observation_timestamp = datetime.now()
        self.init_observation_timestamp = datetime.now()
        self.rate = 0

    def observe(self):
        delta = datetime.now() - self.last_observation_timestamp
        seconds = delta.seconds + delta.microseconds / 1000000
        self.rate = self.value / seconds

    def observe_global_value(self):
        self.last_observation_timestamp = self.init_observation_timestamp()
        super().observe()

    @property
    def pretty(self):
        return f"{get_readable_integer_value(self.rate)}/s"

    @property
    def raw(self):
        return self.rate

    def reset(self):
        self.last_observation_timestamp = datetime.now()
        self.value = 0


class AccumulatedMetricWithPercent(AccumulatedMetric):
    def __init__(self, name, total_metric, **kwargs):
        super().__init__(name, **kwargs)
        self.total_metric = total_metric

    @property
    def pretty(self):
        if self.total_metric.value == 0:
            return "N.A."

        if self.value == 0:
            return "-"

        return f"{round(100*self.value/self.total_metric.value)}%"

    @property
    def raw(self):
        if self.total_metric.value == 0:
            return None

        return self.value / self.total_metric.value

    def reset(self):
        self.value = 0


class SelfAccumulatedMetricWithPercent(AccumulatedMetric):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.total = 0
        self.global_total = 0

    def update(self, value=1):
        self.value += value
        self.total += 1

        self.global_value += value
        self.global_total += 1

    def observe_global_value(self):
        self.total = self.global_total
        self.value = self.global_value
        super().observe()

    @property
    def pretty(self):
        if self.total == 0:
            return "N.A."

        if self.value == 0:
            return "-"

        return f"{round(100*self.value/self.total)}%"

    @property
    def raw(self):
        if self.total == 0:
            return None

        return self.value / self.total

    def reset(self):
        self.value = 0
        self.total = 0


class EllapsedMetric(Metric):
    def __init__(self, name="Ellapsed"):
        super().__init__(name)
        self.start_time = datetime.now()

    def observe(self):
        self.value = datetime.now() - self.start_time


class PerformanceMetric(Metric):
    def __init__(self):

        self.percentiles = {
            "10%": 0.1,
            "50%": 0.5,
            "70%": 0.7,
            "90%": 0.9,
            "99%": 0.99,
        }

        name = self._format(self.percentiles.keys())
        display_length = len(name)
        super().__init__(name=name, display_length=display_length)

        self.count = 0
        self.data = [0 for _ in range(10000)]

        self.global_count = 0
        self.global_data = [0 for _ in range(10000)]

    def _format(self, values):
        return " ".join([f"{v: <4}" for v in values])

    def update(self, value=None):
        ellapsed = min(int(value * 1000), len(self.data) - 1)

        self.data[ellapsed] += 1
        self.count += 1

        self.global_data[ellapsed] += 1
        self.global_count += 1

    def observe(self):
        total = 0

        i_percentiles = iter(self.percentiles.values())
        next_percentile = next(i_percentiles)
        count = self.count
        self.value = []

        if count > 0:
            # for ellapsed in range(len(self.data)):
            # i is ellapsed, value is self.data[ellpased]
            for i, value in enumerate(self.data):
                total += value

                if total / count > next_percentile:
                    self.value.append(i)
                    try:
                        next_percentile = next(i_percentiles)
                    except StopIteration:
                        break

    def observe_global_value(self):
        self.count = self.global_count
        self.data = self.global_data

        super().observe()

    @property
    def pretty(self):
        return self._format(self.value)

    @property
    def raw(self):
        return self.value

    def reset(self):
        self.count = 0
        self.data = [0 for _ in range(10000)]


class Report:
    def __init__(self, logger, report_frequency=5):
        if report_frequency <= 0:
            raise ValueError("Report frequency must be a positive integer")

        self.metric_count = 0
        self.logger = logger
        self.report_frequency = timedelta(seconds=report_frequency)
        self.next_report_timestamp = None

    def start(self):
        self.next_report_timestamp = datetime.now()
        self._compute_next_report_timestamp()

    def _compute_next_report_timestamp(self):
        self.next_report_timestamp += self.report_frequency

    def _is_report_time(self):
        return self.next_report_timestamp < datetime.now()

    def get_headers(self, metrics_getter):
        return [
            (metric.name + " " * 200)[: metric.display_length]
            for metric in metrics_getter()
            if metric.included_in_pulse
        ]

    def print_headers(self, metrics_getter):
        self.logger.info(" ".join(self.get_headers(metrics_getter)))

    def get_pulse_report(self, metrics):
        pretties = []
        raws = []
        print_headers = False

        for metric in metrics:
            metric.observe()
            if metric.included_in_pulse:
                value = metric.pretty

                if metric.has_raw_value and not metric.is_null:
                    raws.append((metric.raw_name, metric.raw))

                if len(value) < metric.display_length:
                    value += " " * (metric.display_length - len(value))
                elif len(value) > metric.display_length:
                    metric.display_length = len(value)
                    print_headers = True

                pretties.append(value)

        for metric in metrics:
            metric.reset()

        return print_headers, pretties, raws

    def signal(self, key, value):
        self.logger.info(f"S {key}: {value}")

    def value(self, key, value):
        self.logger.info(f"V {key}: {value}")

    def pulse(self, metrics_getter, force=False):
        if self._is_report_time() or force:
            metrics = metrics_getter()

            print_headers, pretties, _ = self.get_pulse_report(metrics)

            if print_headers or self.metric_count != len(metrics):
                self.logger.info("")
                self.metric_count = len(metrics)
                self.print_headers(metrics_getter)

            self.logger.info(" ".join(pretties))

            self._compute_next_report_timestamp()

    def done(self, metrics_getter):
        metrics = metrics_getter()

        for metric in metrics:
            metric.observe_global_value()

        _, pretties, _ = self.get_pulse_report(metrics)

        self.logger.info("")
        self.print_headers(metrics_getter)
        self.logger.info(" ".join(pretties))  # TODO, raws=raws)
        self.logger.info("")
        self.logger.info("fuzzing finished")
