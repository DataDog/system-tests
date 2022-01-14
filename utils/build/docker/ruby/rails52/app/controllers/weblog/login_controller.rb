class Weblog::LoginController < ApplicationController
  # bypass devise controlers, because customizing default devise behavior is a nightmare

  protect_from_forgery except: :login

  def new; end

  def new_signup; end

  def login
    user = User.find_by(username: params[:username])

    if user&.authenticate(params[:password])
      sign_in user
      render json: { user: user }
    else
      render json: { error: 'invalid credentials' }, status: 401
    end
  end

  def signup
    user = User.create!(username: params[:username], password: params[:password])
    render json: { user: user }, status: 201
  end
end
