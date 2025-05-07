# frozen_string_literal: true

class SessionsController < Devise::SessionsController
  skip_before_action :verify_authenticity_token

  def create
    sign_out(:user)
    sign_in(:user, User.find('social-security-id'))

    # NOTE: Prevents Rack::Session to re-generate session id again as sign_in
    #       generates a new session id
    request.env['rack.session.options'][:renew] = false

    render plain: session.id
  end
end
