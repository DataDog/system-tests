class RaspSqliController < ApplicationController
  skip_before_action :verify_authenticity_token

  def show
    render plain: "DB request with #{users.size} results"
  end

  private

  def users
    User.find_by_sql("SELECT * FROM users WHERE id='#{params.fetch(:user_id)}'").to_a
  end
end
