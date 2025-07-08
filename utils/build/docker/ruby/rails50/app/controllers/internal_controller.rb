class InternalController < ApplicationController
  def healthcheck
    gemspec = Gem.loaded_specs['datadog'] || Gem.loaded_specs['ddtrace']
    version = gemspec.version.to_s
    version = "#{version}-dev" unless gemspec.source.is_a?(Bundler::Source::Rubygems)

    render json: {
      status: 'ok',
      library: {
        name: 'ruby',
        version: version
      }
    }
  end

  def flush
    # NOTE: If anything needs to be flushed here before the test suite ends,
    #       this is the place to do it.
    Datadog.send(:components)&.telemetry&.flush

    render plain: 'OK'
  end
end
