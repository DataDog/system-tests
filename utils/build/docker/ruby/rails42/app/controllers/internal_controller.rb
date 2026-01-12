class InternalController < ApplicationController
  skip_before_action :verify_authenticity_token

  def healthcheck
    gemspec = Gem.loaded_specs['datadog'] || Gem.loaded_specs['ddtrace']
    version = gemspec.version.to_s
    version = "#{version}-dev" unless gemspec.source.is_a?(Bundler::Source::Rubygems)

    render json: {status: 'ok', library: {name: 'ruby', version: version}}
  end

  def flush
    # NOTE: If anything needs to be flushed here before the test suite ends,
    #       this is the place to do it.
    #       See https://github.com/DataDog/system-tests/blob/64539d1d19d14e0ab040d8e4a01562da1531b7d5/docs/internals/flushing.md
    if telemetry = Datadog.send(:components)&.telemetry
      worker = telemetry.instance_variable_get(:@worker)

      metric_events = worker.instance_variable_get(:@metrics_manager).flush!
      worker.send(:flush_events, metric_events) if metric_events.any?

      sleep 0.2
    end

    if open_feature = Datadog.send(:components)&.open_feature
      worker = open_feature.instance_variable_get(:@worker)
      worker.send(:send_events, *worker.dequeue)
    end

    render plain: 'OK'
  end
end
