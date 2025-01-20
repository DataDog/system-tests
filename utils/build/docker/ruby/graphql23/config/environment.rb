# Load the Rails application.
require_relative "application"

# We have to change the GraphQL tracer method early, as auto instrumentation is enabled.
# This can be removed once the unified GraphQL tracer is the default.
# TODO: Remove env var in `datadog` gem version 3.0
ENV['DD_TRACE_GRAPHQL_WITH_UNIFIED_TRACER'] = '1'

# Initialize the Rails application.
Rails.application.initialize!
