# frozen_string_literal: true

require 'open_feature/sdk'
require 'datadog/open_feature/provider'

class OpenfeatureController < ApplicationController
  skip_before_action :verify_authenticity_token

  def evaluate
    # TODO: Clarify the expectation of the interface
    OpenFeature::SDK.set_provider(Datadog::OpenFeature::Provider.new)

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
        targeting_key: args.targeting_key, **args.attributes
      )
      options = {
        flag_key: args.flag, default_value: args.default_value, evaluation_context: context
      }

      value =
        case variation_type
        when 'BOOLEAN'then client.fetch_boolean_value(**options)
        when 'STRING' then client.fetch_boolean_value(**options)
        when 'INTEGER' then client.fetch_boolean_value(**options)
        when 'NUMERIC' then client.fetch_boolean_value(**options)
        when 'JSON' then client.fetch_boolean_value(**options)
        else default_value
        end

      res.write({value: value, reason: 'DEFAULT'}.to_json)
    rescue
      res.write({value: args.default_value, reason: 'ERROR'}.to_json)
    end
  end
end
