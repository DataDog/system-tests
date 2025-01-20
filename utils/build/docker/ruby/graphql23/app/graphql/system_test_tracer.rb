# frozen_string_literal: true

module SystemTestTracer
  include Datadog::AppSec::Contrib::GraphQL::AppSecTrace

  def prepare_span(key, data, span)
    span.set_tag('graphql.custom_tag.works', 'true')
  end
end
