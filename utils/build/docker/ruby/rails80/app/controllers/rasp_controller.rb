class RaspController < ApplicationController
  skip_before_action :verify_authenticity_token

  def ssrf
    url = URI.parse(params.fetch(:domain))
    url = "http://#{url}" unless url.scheme

    Faraday.get(url)

    head :ok
  end

  def sqli
    users = User.find_by_sql(
      "SELECT * FROM users WHERE id='#{params.fetch(:user_id)}'"
    ).to_a

    render plain: "DB request with #{users.size} results"
  end

  def external_request
    status = params.fetch(:status, "200")
    url_extra = params.fetch(:url_extra, "")

    headers = {}
    params.except(:controller, :action, :status, :url_extra).each do |key, value|
      headers[key.to_s] = value.to_s
    end

    body = request.body.read
    headers["Content-Type"] = request.content_type if body.present?

    url = "http://internal_server:8089/mirror/#{status}#{url_extra}"
    response = Faraday.new.run_request(request.request_method.downcase.to_sym, url, body, headers)

    if (200..299).cover?(response.status)
      render json: {status: response.status, payload: JSON.parse(response.body), headers: response.headers}
    else
      render json: {status: response.status, error: "Request failed"}
    end
  rescue => e
    render json: {status: 599, error: "#{e.class}: #{e.message} (#{e.backtrace[0]})"}
  end
end
