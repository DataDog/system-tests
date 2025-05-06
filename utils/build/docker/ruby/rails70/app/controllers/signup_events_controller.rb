# frozen_string_literal: true

require 'devise'

class SignupEventsController < Devise::RegistrationsController
  skip_before_action :verify_authenticity_token

  # POST /signup
  def create
    build_resource(sign_up_params)
    resource.id = 'new-user'
    resource.save

    # NOTE: In the current test suite we don't have management of the scenario
    #       with authentication after signup. Hence, I'm incorporating a hack
    #       to emulate :confirmable stategy, but avoid email send-outs.
    resource.instance_eval do
      def active_for_authentication?
        false
      end
    end

    yield(resource) if block_given?

    if resource.persisted?
      if resource.active_for_authentication?
        sign_up(resource_name, resource)
      else
        expire_data_after_sign_in!
      end
    else
      clean_up_passwords(resource)
      set_minimum_password_length
    end

    render plain: 'Hello, world!'
  end
end
