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

  get '/params/:value' => 'system_test#handle_path_params'
  get '/spans' => 'system_test#generate_spans'
  get '/status' => 'system_test#status'
  get '/read_file' => 'system_test#read_file'
  get '/make_distant_call' => 'system_test#make_distant_call'

  get '/headers' => 'system_test#test_headers'
  get  '/identify' => 'system_test#identify'

  get 'user_login_success_event' => 'system_test#user_login_success_event'
  get 'user_login_failure_event' => 'system_test#user_login_failure_event'
  get 'custom_event' => 'system_test#custom_event'

  %i(get post).each do |request_method|
    send(request_method, '/tag_value/:tag_value/:status_code' => 'system_test#tag_value')
  end

  match '/tag_value/:tag_value/:status_code' => 'system_test#tag_value', via: :options

  get '/users' => 'system_test#users'

  %i(get post).each do |request_method|
    # We have to provide format: false to make sure the Test_DiscoveryScan test do not break
    # https://github.com/DataDog/system-tests/blob/515310b5fb1fd0792fc283c9ee134ab3803d6e7c/tests/appsec/waf/test_rules.py#L374
    # The test hits '/login.pwd' and expects a 404. By default rails parse format by default and consider the route to exists. We want want onlt '/login' to exists
    send(request_method, '/login' => 'system_test#login', format: false)
  end

  post '/graphql', to: 'graphql#execute'

  get '/sample_rate_route/:i' => 'system_test#sample_rate_route'
end
