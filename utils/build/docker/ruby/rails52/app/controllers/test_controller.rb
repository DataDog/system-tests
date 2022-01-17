class TestController < ApplicationController
  before_action :tag_with_identify
  before_action { logger.debug { 'before_action' } }
  after_action  { logger.debug { 'after_action' } }

  def ping
    @output = "PONG"
    rawify
  end

  def eval
    @output = Kernel.eval("#{params[:input]}") if params.key?(:input)
    rawify
  end

  def shi
    @output = `ls #{Dir.pwd}/#{params[:input]}` if params.key?(:input)
    rawify
  end

  def sqli
    @output = Foo.where("key = '#{params[:input]}'").to_a if params.key?(:input)
    rawify
  end

  def lfi
    @output = File.read(File.join('public', params[:input] || '404.html'))
    rawify
  end

  def identify
    @output = 'identified'
    rawify
  end

  def auth
    @output = 'auth'
    rawify
  end

  def signup
    @output = 'signup'
    rawify
  end

  def track
    @output = params[:input]
    rawify
  end

  def tracing
    body = Net::HTTP.get(URI(params[:input] || 'http://example.com'))
    @output = body
    rawify
  end

  def upload
    case request.headers['Content-Type']
    when 'application/octet-stream'
      data = request.body.read
      filename = nil
      @output = ''
      @output << "- size: #{data.size}\n"
    when /^multipart\/form-data/
      uploads = params.select { |k, v| v.is_a?(ActionDispatch::Http::UploadedFile) }
      @output = ''
      uploads.each do |key, upload|
        data = upload.read
        filename = upload.original_filename
        content_type = upload.content_type
        @output << "- key: #{key}\n"
        @output << "  filename: #{filename}\n"
        @output << "  content-type: #{content_type}\n"
        @output << "  size: #{data.size}\n"
      end
    end
    rawify
  end

  private

  def tag_with_identify
  end

  def rawify
    if params[:raw]
      render plain: @output.to_s
    else
      render 'generic'
    end
  end
end
