FROM arm32v7/ruby:latest

# print versions
RUN ruby --version && curl --version

# install hello world app
RUN mkdir /app
WORKDIR /app

RUN echo "source 'https://rubygems.org'\n\
gem 'sinatra'\n\
gem 'rack-contrib'\n\
gem 'puma'\n" > Gemfile

RUN bundle install

RUN echo "require 'sinatra/base'\n\
require 'rack'\n\
require 'rack/contrib'\n\
require 'ddtrace/auto_instrument'\n\
Datadog.tracer.trace('init.service') do |span|\n\
end\n\
class MyApp < Sinatra::Base\n\
    register Datadog::Contrib::Sinatra::Tracer\n\
    use Rack::PostBodyContentTypeParser\n\
    set :environment, :production\n\
    set :show_exceptions, false\n\
    set :port, 7777\n\
    set :bind, '0.0.0.0'\n\
    get '/' do\n\
        'Hello world!'\n\
    end\n\
    get '/sample_rate_route/:i' do\n\
        'OK'\n\
    end\n\
end\n\
" > app.rb

RUN echo "require File.expand_path('app', File.dirname(__FILE__))\n\
run MyApp\n" > config.ru

# docker startup
CMD bundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# Datadog setup
ENV DD_TRACE_SAMPLE_RATE=0.5

# docker build -f utils/build/docker/ruby.sinatra-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
