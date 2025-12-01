Rails.application.routes.draw do
  # For details on the DSL available within this file, see http://guides.rubyonrails.org/routing.html

  class ResourceRenamingRackApp
    def call(_env)
      [200, {'Content-Type' => 'text/plain'}, ['OK']]
    end
  end
  mount ResourceRenamingRackApp.new => '/resource_renaming'

  get  '/' => 'system_test#root'
  post '/' => 'system_test#root'

  get '/healthcheck' => 'internal#healthcheck'
  get '/flush' => 'internal#flush'

  get  '/waf' => 'system_test#waf'
  post '/waf' => 'system_test#waf'
  get  '/waf/*other' => 'system_test#waf'
  post '/waf/*other' => 'system_test#waf'

  get '/params/:value' => 'system_test#handle_path_params'
  get '/spans' => 'system_test#generate_spans'
  get '/status' => 'system_test#status'
  get '/make_distant_call' => 'system_test#make_distant_call'

  get '/headers' => 'system_test#test_headers'
  get '/identify' => 'system_test#identify'

  get 'user_login_success_event' => 'business_logic_events#user_login_success_event'
  get 'user_login_failure_event' => 'business_logic_events#user_login_failure_event'
  get 'custom_event' => 'business_logic_events#custom_event'
  post 'user_login_success_event_v2' => 'business_logic_events#user_login_success_event_v2'
  post 'user_login_failure_event_v2' => 'business_logic_events#user_login_failure_event_v2'

  %i[get post].each do |request_method|
    send(request_method, '/tag_value/:tag_value/:status_code' => 'system_test#tag_value')
  end
  match '/tag_value/:tag_value/:status_code' => 'system_test#tag_value', via: :options
  get '/users' => 'system_test#users'

  devise_for :users, skip: :all
  devise_scope :user do
    get '/login' => 'login_events#create', format: false

    post '/login' => 'login_events#create', format: false
    post '/signup' => 'signup_events#create', format: false

    get 'session/new' => 'sessions#create'
  end

  get '/requestdownstream' => 'system_test#request_downstream'
  get '/returnheaders' => 'system_test#return_headers'

  get '/rasp/sqli' => 'rasp_sqli#show'
  post '/rasp/sqli' => 'rasp_sqli#show'

  get '/rasp/ssrf' => 'rasp_ssrf#show'
  post '/rasp/ssrf' => 'rasp_ssrf#show'

  get '/sample_rate_route/:i' => 'api_security#sample_rate_route'
  get '/api_security_sampling/:i' => 'api_security#sampling_by_path'
  get '/api_security/sampling/:status' => 'api_security#sampling_by_status'
end
