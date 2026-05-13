Rails.application.routes.draw do
  root to: proc { [200, {}, ['OK']] }
  get 'crashme', controller: 'datadog', action: :crashme
  get 'fork_and_crash', controller: 'datadog', action: :fork_and_crash
  get 'child_pids', controller: 'datadog', action: :child_pids
  get 'zombies', controller: 'datadog', action: :zombies
end
