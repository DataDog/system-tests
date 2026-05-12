# frozen_string_literal: true

require 'open_feature/sdk'
require 'datadog/open_feature/provider'

OpenFeature::SDK.configure do |config|
  config.set_provider(Datadog::OpenFeature::Provider.new)
end
