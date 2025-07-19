require 'timeout'

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
      telemetry.instance_variable_get(:@worker)&.loop_wait_time = 0

      # HACK: In the current implementation there is no way to force the flushing.
      #       Instead we are giving us a fraction of time after setting `loop_wait_time`
      #       and just wait till all penging messages are flushed.
      #
      # NOTE: Be aware that system-tests doesn't like slow responses, so change that
      #       value carefully.
      sleep 0.2
    end

    render plain: 'OK'
  end
end
