from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import OciDigestResolver

DEFAULT_IMAGE = "otel/opentelemetry-collector-contrib:0.137.0"


class Dev(SimpleTarget):
    inputs = (
        OciDigestResolver(
            name="collector_image",
            image=DEFAULT_IMAGE,
            variable_name="OTEL_COLLECTOR_IMAGE",
        ),
    )
    entries = (text_entry("otel_collector-image", "{collector_image.reference}"),)


class Prod(SimpleTarget):
    inputs = (OciDigestResolver(name="collector_image", image=DEFAULT_IMAGE),)
    entries = (text_entry("otel_collector-image", "{collector_image.reference}"),)
