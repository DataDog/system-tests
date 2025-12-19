# frozen_string_literal: true

require 'openfeature/sdk'
require 'datadog/open_feature/provider'

class OpenFeatureController < ApplicationController
  skip_before_action :verify_authenticity_token

  def start
    OpenFeature::SDK.set_provider(Datadog::OpenFeature::Provider.new)

    # NOTE: There is no set_provider_and_wait in OpenFeature::SDK
    loop do
      break unless Datadog::OpenFeature.evaluator.ufc_json.nil?
      sleep 0.1
    end

    render json: {}
  end

  def evaluate
    client = OpenFeature::SDK.build_client

    payload = JSON.parse(request.body.string)
    args = {
      flag: payload['flag'],
      variation_type: payload['variationType'],
      default_value: payload['defaultValue'],
      targeting_key: payload['targetingKey'],
      attributes: payload['attributes']
    }

    begin
      context = OpenFeature::SDK::EvaluationContext.new(
        targeting_key: args[:targeting_key], **args[:attributes]
      )
      options = {
        flag_key: args[:flag], default_value: args[:default_value], evaluation_context: context
      }

      value =
        case args[:variation_type]
        when 'BOOLEAN'then client.fetch_boolean_value(**options)
        when 'STRING' then client.fetch_string_value(**options)
        when 'INTEGER' then client.fetch_integer_value(**options)
        when 'NUMERIC' then client.fetch_numeric_value(**options)
        when 'JSON' then client.fetch_object_value(**options)
        else 'FATAL_UNEXPECTED_VARIATION_TYPE'
        end

      render json: {value: value, reason: 'DEFAULT'}
    rescue
      render json: {value: args[:default_value], reason: 'ERROR'}
    end
  end
end
