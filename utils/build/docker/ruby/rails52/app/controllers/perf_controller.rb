class PerfController < ApplicationController
  def sqli

    sleep(params[:lag].to_f) if params[:lag]

    keys = Foo.pluck(:key)

    @output = keys.map do |k|
      sleep(params[:pace].to_f) if params[:pace]
      Foo.where("key = '#{params[:input] || k}'").first
      #Kernel.`('echo foo')
      #Struct.new(:key, :value).new(0, 0)
    end

    rawify
  end

  private

  def rawify
    if params[:raw]
      render plain: @output.to_s
    else
      render 'generic'
    end
  end
end
