# frozen_string_literal: true

require 'openfeature/sdk'
require 'datadog/open_feature/provider'

class OpenfeatureController < ApplicationController
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
    puts request.body

    client = OpenFeature::SDK.build_client

    payload = JSON.parse(request.body.string)
    args = {flag_key: flag_key, default_value: default_value, evaluation_context: context}

    begin
      value =
        case variation_type
        when 'BOOLEAN'then client.fetch_boolean_value(**args)
        when 'STRING' then client.fetch_boolean_value(**args)
        when 'INTEGER' then client.fetch_boolean_value(**args)
        when 'NUMERIC' then client.fetch_boolean_value(**args)
        when 'JSON' then client.fetch_boolean_value(**args)
        else default_value
        end

      render json: {value: value, reason: 'DEFAULT'}
    rescue
      render json: {value: default_value, reason: 'ERROR'}
    end
  end
end
