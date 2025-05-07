Rails.application.routes.draw do
  # Define your application routes per the DSL in https://guides.rubyonrails.org/routing.html

  # Defines the root path route ("/")
  # root "articles#index"

  get  '/' => 'system_test#root'
  post '/' => 'system_test#root'

  get  '/healthcheck' => 'system_test#healthcheck'

  get  '/waf' => 'system_test#waf'
  post '/waf' => 'system_test#waf'
  get  '/waf/*other' => 'system_test#waf'
  post '/waf/*other' => 'system_test#waf'

  get '/kafka/produce' => 'system_test#kafka_produce'
  get '/kafka/consume' => 'system_test#kafka_consume'

  get '/params/:value' => 'system_test#handle_path_params'
  get '/spans' => 'system_test#generate_spans'
  get '/status' => 'system_test#status'
  get '/read_file' => 'system_test#read_file'
  get '/make_distant_call' => 'system_test#make_distant_call'
  get '/log/library' => 'system_test#log_library'

  get '/headers' => 'system_test#test_headers'
  get '/identify' => 'system_test#identify'

  get 'user_login_success_event' => 'system_test#user_login_success_event'
  get 'user_login_failure_event' => 'system_test#user_login_failure_event'
  get 'custom_event' => 'system_test#custom_event'

  %i[get post].each do |request_method|
    send(request_method, '/tag_value/:tag_value/:status_code' => 'system_test#tag_value')
  end
  match '/tag_value/:tag_value/:status_code' => 'system_test#tag_value', via: :options
  get '/users' => 'system_test#users'

  devise_for :users, skip: :all
  devise_scope :user do
    # We have to provide format: false to make sure the Test_DiscoveryScan test do not break
    # https://github.com/DataDog/system-tests/blob/515310b5fb1fd0792fc283c9ee134ab3803d6e7c/tests/appsec/waf/test_rules.py#L374
    # The test hits '/login.pwd' and expects a 404.
    # By default rails parse format by default and consider the route to exists. We want want only '/login' to exists
    get '/login' => 'login_events#create', format: false
    post '/login' => 'login_events#create', format: false
    post '/signup' => 'signup_events#create', format: false
  end

  get '/requestdownstream' => 'system_test#request_downstream'
  get '/returnheaders' => 'system_test#return_headers'

  get '/otel_drop_in_default_propagator_extract' => 'system_test#otel_drop_in_default_propagator_extract'
  get '/otel_drop_in_default_propagator_inject' => 'system_test#otel_drop_in_default_propagator_inject'

  get '/debugger/init' => 'debugger#init'
  get '/debugger/pii' => 'debugger#pii'
  get '/debugger/log' => 'debugger#log_probe'
  get '/debugger/mix/:string_arg/:int_arg' => 'debugger#mix_probe'

  get '/rasp/sqli' => 'rasp_sqli#show'
  post '/rasp/sqli' => 'rasp_sqli#show'

  get '/rasp/ssrf' => 'rasp_ssrf#show'
  post '/rasp/ssrf' => 'rasp_ssrf#show'

  get '/sample_rate_route/:i' => 'system_test#sample_rate_route'
end
