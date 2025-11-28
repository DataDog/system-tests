Rails.application.routes.draw do
  # For details on the DSL available within this file, see https://guides.rubyonrails.org/routing.html

  # Defines the root path route ("/")
  # root "articles#index"
  get 'fork_and_crash', controller: 'datadog', action: :fork_and_crash
  get 'child_pids', controller: 'datadog', action: :child_pids
  get 'zombies', controller: 'datadog', action: :zombies
end
