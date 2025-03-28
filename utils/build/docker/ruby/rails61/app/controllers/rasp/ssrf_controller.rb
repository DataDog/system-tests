class RASP::SSRFController < ApplicationController
  skip_before_action :verify_authenticity_token

  def show
    perform_http_request(params.fetch(:domain))

    head :ok
  end

  def create
    perform_http_request(params.fetch(:url))

    head :ok
  end

  private

  def perform_http_request(url)
    url = URI.parse(url_param)
    url = "https://#{url}" unless url.scheme

    Faraday.get(url)
  end
end
