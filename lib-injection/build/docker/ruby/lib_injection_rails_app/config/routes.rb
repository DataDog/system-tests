Rails.application.routes.draw do
  # Define your application routes per the DSL in https://guides.rubyonrails.org/routing.html

  # Defines the root path route ("/")
  # root "articles#index"
  get 'fork_and_crash', controller: 'datadog', action: :fork_and_crash
  get 'child_pids', controller: 'datadog', action: :child_pids
end
