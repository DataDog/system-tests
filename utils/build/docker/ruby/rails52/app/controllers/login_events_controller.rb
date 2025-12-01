# frozen_string_literal: true

require 'devise'
require 'datadog/kit/appsec/events'

class LoginEventsController < Devise::SessionsController
  skip_before_action :verify_authenticity_token

  # POST /login
  # GET /login (basic)
  def create
    sdk_event = request.params[:sdk_event]
    sdk_user = request.params[:sdk_user]
    sdk_email = request.params[:sdk_mail]
    sdk_exists = request.params[:sdk_user_exists] == "true"

    if sdk_event === 'failure' && sdk_user
      metadata = {}
      metadata[:email] = sdk_email if sdk_email

      Datadog::Kit::AppSec::Events.track_login_failure(user_id: sdk_user, user_exists: sdk_exists, **metadata)
    elsif sdk_event === 'success' && sdk_user
      user = { id: sdk_user }
      user[:email] = sdk_email if sdk_email

      Datadog::Kit::AppSec::Events.track_login_success(user: user)
    end

    self.resource = warden.authenticate!(auth_options)
    sign_in(resource_name, resource)
    yield(resource) if block_given?

    render plain: 'Hello, world!'
  end
end
