# frozen_string_literal: true

class OpenFeatureController < ApplicationController
  skip_before_action :verify_authenticity_token

  def start
    OpenFeature::SDK.set_provider_and_wait(Datadog::OpenFeature::Provider.new)
    render json: {}
  rescue => e
    render json: {error: e.message}, status: :internal_server_error
  end

  PROVIDER_OPTIONS = %i[evaluation_telemetry_enabled exposures_enabled].freeze
  OPTION_CLIENTS = {}
  OPTION_CLIENTS_MUTEX = Mutex.new

  def evaluate
    render_evaluation(OpenFeature::SDK.build_client, JSON.parse(request.body.string))
  end

  # Evaluates like #evaluate, through an OpenFeature domain whose provider is built with the requested
  # options, one provider per combination. SDKs without the options answer 501.
  def evaluate_with_provider_options
    payload = JSON.parse(request.body.string)
    unsupported = PROVIDER_OPTIONS - provider_keywords
    unless unsupported.empty?
      return render json: {errorCode: 'UNSUPPORTED', errorMessage: "Provider.new does not support #{unsupported.join(', ')}"},
        status: :not_implemented
    end

    options = {
      evaluation_telemetry_enabled: payload['evaluationTelemetryEnabled'] != false,
      exposures_enabled: payload['exposuresEnabled'] != false
    }
    render_evaluation(option_client(options), payload)
  rescue => e
    render json: {errorCode: 'GENERAL', errorMessage: e.message}, status: :internal_server_error
  end

  private

  def provider_keywords
    Datadog::OpenFeature::Provider.instance_method(:initialize).parameters
      .select { |type, _| type == :key || type == :keyreq }.map(&:last)
  end

  def option_client(options)
    domain = "telemetry-#{options[:evaluation_telemetry_enabled]}-exposures-#{options[:exposures_enabled]}"
    OPTION_CLIENTS_MUTEX.synchronize do
      OPTION_CLIENTS[domain] ||= begin
        OpenFeature::SDK.set_provider_and_wait(Datadog::OpenFeature::Provider.new(**options), domain: domain)
        OpenFeature::SDK.build_client(domain: domain)
      end
    end
  end

  def render_evaluation(client, payload)
    args = {
      flag: payload['flag'],
      variation_type: payload['variationType'],
      default_value: payload['defaultValue'],
      targeting_key: payload['targetingKey'],
      targeting_keys: payload['targetingKeys'],
      attributes: payload['attributes']
    }

    begin
      targeting_keys =
        if args[:targeting_keys].is_a?(Array) && !args[:targeting_keys].empty?
          args[:targeting_keys]
        else
          [args[:targeting_key]]
        end
      value = nil

      targeting_keys.each do |targeting_key|
        context = OpenFeature::SDK::EvaluationContext.new(
          targeting_key: targeting_key, **args[:attributes]
        )
        options = {
          flag_key: args[:flag], default_value: args[:default_value], evaluation_context: context
        }

        value =
          case args[:variation_type]
          when 'BOOLEAN'then client.fetch_boolean_value(**options)
          when 'STRING' then client.fetch_string_value(**options)
          when 'INTEGER' then client.fetch_integer_value(**options)
          when 'NUMERIC' then client.fetch_float_value(**options)
          when 'JSON' then client.fetch_object_value(**options)
          else 'FATAL_UNEXPECTED_VARIATION_TYPE'
          end
      end

      render json: {value: value, reason: 'DEFAULT', count: targeting_keys.length}
    rescue
      render json: {value: args[:default_value], reason: 'ERROR'}
    end
  end
end
