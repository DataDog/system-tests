from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import NpmLatestResolver

PACKAGE_NAME = "@opentelemetry/auto-instrumentations-node"


class Dev(SimpleTarget):
    inputs = (NpmLatestResolver(name="otel_package", package=PACKAGE_NAME),)
    entries = (text_entry("nodejs-otel-load-from-npm", f"{PACKAGE_NAME}@{{otel_package.version}}"),)


class Prod(Dev):
    pass
