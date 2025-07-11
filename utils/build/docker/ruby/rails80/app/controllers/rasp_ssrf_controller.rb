class RaspSsrfController < ApplicationController
  skip_before_action :verify_authenticity_token

  def show
    perform_http_request(params.fetch(:domain))

    head :ok
  end

  private

  def perform_http_request(domain_param)
    url = URI.parse(domain_param)
    url = "http://#{url}" unless url.scheme

    Faraday.get(url)
  end
end
