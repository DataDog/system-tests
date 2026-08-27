from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import PypiLatestResolver

PACKAGE_NAME = "opentelemetry-distro"


class Dev(SimpleTarget):
    inputs = (PypiLatestResolver(name="otel_package", package=PACKAGE_NAME),)
    entries = (text_entry("python-otel-load-from-pip", f"{PACKAGE_NAME}[otlp]=={{otel_package.version}}"),)


class Prod(Dev):
    pass
