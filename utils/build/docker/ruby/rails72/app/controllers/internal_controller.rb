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
      if worker = telemetry.instance_variable_get(:@worker)
        # NOTE: We are flushing telemetry metrics manually.
        if metrics_manager = worker.instance_variable_get(:@metrics_manager)
          metric_events = metrics_manager.flush!
          worker.send(:flush_events, metric_events) if metric_events.any?
        end

        # HACK: In the current implementation there is no way to force the flushing.
        #       Instead we are giving us a fraction of time after setting `loop_wait_time`
        #       and just wait till all penging messages are flushed.
        #
        # NOTE: Be aware that system-tests doesn't like slow responses, so change that
        #       value carefully.
        worker.loop_wait_time = 0
        sleep 0.2
      end
    end

    # NOTE: We don't expose directly flushing in the OpenFeature component as it
    #       has no use now. But this might change, but for now we are going to
    #       flush manually knowing some internals.
    if open_feature = Datadog.send(:components)&.open_feature
      worker = open_feature.instance_variable_get(:@worker)
      worker.send(:send_events, *worker.dequeue)
    end

    render plain: 'OK'
  end
end
