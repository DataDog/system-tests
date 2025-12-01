require 'json'

require 'datadog/kit/appsec/events'
require 'datadog/kit/appsec/events/v2'

class BusinessLogicEventsController < ApplicationController
  skip_before_action :verify_authenticity_token

  def user_login_success_event
    Datadog::Kit::AppSec::Events.track_login_success(
      Datadog::Tracing.active_trace,
      user: {id: 'system_tests_user'},
      metadata0: "value0",
      metadata1: "value1"
    )

    render plain: 'Hello, world!'
  end

  def user_login_failure_event
    Datadog::Kit::AppSec::Events.track_login_failure(
      Datadog::Tracing.active_trace,
      user_id: 'system_tests_user',
      user_exists: true,
      metadata0: "value0",
      metadata1: "value1"
    )

    render plain: 'Hello, world!'
  end

  def custom_event
    Datadog::Kit::AppSec::Events.track(
      'system_tests_event',
      Datadog::Tracing.active_trace,
      metadata0: "value0",
      metadata1: "value1"
    )

    render plain: 'Hello, world!'
  end

  def user_login_success_event_v2
    payload = params.to_unsafe_h

    Datadog::Kit::AppSec::Events::V2.track_user_login_success(
      payload['login'],
      payload['user_id'],
      payload.fetch('metadata', {}).symbolize_keys
    )

    render plain: 'OK'
  end

  def user_login_failure_event_v2
    payload = params.to_unsafe_h

    Datadog::Kit::AppSec::Events::V2.track_user_login_failure(
      payload['login'],
      payload.fetch('exists', 'false') == 'true',
      payload.fetch('metadata', {}).symbolize_keys
    )

    render plain: 'OK'
  end
end
