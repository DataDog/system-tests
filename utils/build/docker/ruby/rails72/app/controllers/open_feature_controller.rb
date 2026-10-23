# frozen_string_literal: true

class OpenFeatureController < ApplicationController
  skip_before_action :verify_authenticity_token

  def start
    OpenFeature::SDK.set_provider_and_wait(Datadog::OpenFeature::Provider.new)
    render json: {}
  rescue => e
    render json: {error: e.message}, status: :internal_server_error
  end

  def evaluate
    client = OpenFeature::SDK.build_client

    payload = JSON.parse(request.body.string)
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
      details = nil

      targeting_keys.each do |targeting_key|
        context = OpenFeature::SDK::EvaluationContext.new(
          targeting_key: targeting_key, **args[:attributes]
        )
        options = {
          flag_key: args[:flag], default_value: args[:default_value], evaluation_context: context
        }

        details =
          case args[:variation_type]
          when 'BOOLEAN' then client.fetch_boolean_details(**options)
          when 'STRING' then client.fetch_string_details(**options)
          when 'INTEGER' then client.fetch_integer_details(**options)
          when 'NUMERIC' then client.fetch_float_details(**options)
          when 'JSON' then client.fetch_object_details(**options)
          else
            return render json: {value: 'FATAL_UNEXPECTED_VARIATION_TYPE', reason: 'DEFAULT', count: targeting_keys.length}
          end
      end

      return render json: {value: nil, reason: 'DEFAULT', count: 0} if details.nil?

      metadata = details.flag_metadata || {}
      render json: {
        value: details.value,
        reason: details.reason,
        errorCode: details.error_code,
        variant: details.variant,
        flagMetadata: metadata,
        allocationKey: metadata['__dd_allocation_key'],
        count: targeting_keys.length
      }
    rescue
      render json: {value: args[:default_value], reason: 'ERROR'}
    end
  end
end
