class ApiController < ActionController::API
  def ping
    render json: ["200 OK"]
  end

  def shi
    render json: { params[:input] => `ls #{Dir.pwd}/tmp/#{params[:input]}` }
  end

  def sqli
    render json: Foo.where("key = '#{params[:input]}'").to_a
  end

  def redacted
    render json: Foo.where("key = '#{params[:password]}'").to_a
  end
end
