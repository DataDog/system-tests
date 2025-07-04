class ApiSecurityController < ApplicationController
  skip_before_action :verify_authenticity_token

  def sample_rate_route
    render plain: 'OK'
  end

  def sampling_by_path
    render plain: 'Hello!'
  end

  def sampling_by_status
    render plain: 'OK', status: params.fetch(:status, 200).to_i
  end
end 