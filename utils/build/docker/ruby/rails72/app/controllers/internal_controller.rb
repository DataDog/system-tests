require 'timeout'

class InternalController < ApplicationController
  FLUSH_MAX_WAIT_S = 8

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
    #
    # WARNING: To be able to respond on time to the system-tests we are flushing
    #          and time-boxing us to time less than system-tests allows
    #          See: https://github.com/DataDog/system-tests/blob/7d555e474e6ce32825dd79c1b65ac64805ab09a8/utils/_context/_scenarios/endtoend.py#L547
    begin
      Timeout.timeout(FLUSH_MAX_WAIT_S) { Datadog.send(:components)&.telemetry&.flush }
    rescue Timeout::Error
      Rails.logger.warn("Unable to flush telemetry within `#{seconds}` second(s)")
    end

    render plain: 'OK'
  end
end 