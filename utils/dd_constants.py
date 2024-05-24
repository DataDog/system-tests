"""Key used in the metrics map to indicate tracer sampling priority"""
SAMPLING_PRIORITY_KEY = "_sampling_priority_v1"

"""
Key used in the metrics to map to single span sampling.
"""
SINGLE_SPAN_SAMPLING_MECHANISM = "_dd.span_sampling.mechanism"

"""
Value used in the metrics to map to single span sampling decision.
"""
SINGLE_SPAN_SAMPLING_MECHANISM_VALUE = 8

"""Key used in the metrics to map to single span sampling sample rate."""
SINGLE_SPAN_SAMPLING_RATE = "_dd.span_sampling.rule_rate"

"""Key used in the metrics to map to single span sampling max per second."""
SINGLE_SPAN_SAMPLING_MAX_PER_SEC = "_dd.span_sampling.max_per_second"


""" Some release identifiers """
PYTHON_RELEASE_PUBLIC_BETA = "1.4.0rc1.dev"
PYTHON_RELEASE_GA_1_1 = "1.5.0rc1.dev"
