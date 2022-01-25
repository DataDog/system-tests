Rails.application.routes.draw do

  get     'html/ping'        => 'test#ping'
  get     'html/shi'         => 'test#shi'
  post    'html/shi'         => 'test#shi'
  get     'html/sqli'        => 'test#sqli'
  post    'html/sqli'        => 'test#sqli'
  get     'html/lfi'         => 'test#lfi',           defaults: { input: '404.html' }
  post    'html/lfi'         => 'test#lfi'
  get     'html/identify'    => 'test#identify'
  get     'html/auth'        => 'test#auth'
  get     'html/signup'      => 'test#signup'
  get     'html/sqli/perf'   => 'perf#sqli'
  post    'html/sqli/perf'   => 'perf#sqli'
  get     'html/tracing'     => 'test#tracing'

  get     'html/waf/*'       => 'test#ping'
  post    'html/waf/*'       => 'test#ping'
  put     'html/waf/*'       => 'test#ping'
  delete  'html/waf/*'       => 'test#ping'

  get     'raw/ping'         => 'test#ping',          defaults: { raw: true }
  post    'raw/shi'          => 'test#shi',           defaults: { raw: true }
  post    'raw/sqli'         => 'test#sqli',          defaults: { raw: true }
  get     'raw/identify'     => 'test#identify',      defaults: { raw: true }
  get     'raw/sqli/perf'    => 'perf#sqli',          defaults: { raw: true }
  post    'raw/sqli/perf'    => 'perf#sqli',          defaults: { raw: true }
  get     'raw/tracing'      => 'test#tracing',       defaults: { raw: true }
  post    'raw/upload'       => 'test#upload',        defaults: { raw: true }
  put     'raw/upload'       => 'test#upload',        defaults: { raw: true }
  get     'raw/passlisted'   => 'test#ping',          defaults: { raw: true }

  get     'api/ping'         => 'api#ping'
  post    'api/shi'          => 'api#shi'
  post    'api/sqli'         => 'api#sqli'
  post    'api/redacted'     => 'api#redacted'


  post    '/graphql'         => 'graphql#execute'
  mount GraphiQL::Rails::Engine, at: '/graphiql', graphql_path: '/graphql' if Rails.env.development?

  # Rack nesting test
  match '/nested/rack' => NestedRackApp.new,
        :anchor => false,
        :via => [:get, :post]
  match '/nested/sinatra' => NestedSinatraApp.new,
        :anchor => false,
        :via => [:get, :post]

  # old weblog API
  scope '/weblog', module: 'weblog' do
    get  '/' => 'system_tests#root'
    post '/' => 'system_tests#root'

    # /eval
    get  '/eval' => 'system_tests#evali'
    post '/eval' => 'system_tests#evali'

    # /graphql
    get  '/graphql' => 'system_tests#graphql'
    post '/graphql' => 'system_tests#graphql'

    # /lfi
    get  '/lfi' => 'system_tests#lfi'
    post '/lfi' => 'system_tests#lfi'

    # /files
    get  '/files/:q' => 'system_tests#lfi', constraints: { q: /.+/ }

    # /items
    post '/items/find' => 'system_tests#mongo'

    # /su
    get '/su/:id/:target' => 'system_tests#su'

    # /posts
    get '/posts/:id' => 'system_tests#sqli'

    # /exec
    get  '/exec' => 'system_tests#webshell'
    post '/exec' => 'system_tests#webshell'

    # /shellshock
    get  '/shellshock' => 'system_tests#shellshock'
    post '/shellshock' => 'system_tests#shellshock'

    # /ping
    get  'ping'    => 'system_tests#ping'
    get  'ping/:q' => 'system_tests#ping', constraints: { q: /.+/ }

    # /ssrf
    get  '/ssrf/:id' => 'system_tests#ssrf', constraints: { id: /.+/ }

    # /waf
    get  '/waf' => 'system_tests#root'
    post '/waf' => 'system_tests#root'

    # /xss
    get  '/xss' => 'system_tests#xss'
    post '/xss' => 'system_tests#xss'

    # /xxe
    get  '/xxe' => 'system_tests#xxe'
    post '/xxe' => 'system_tests#xxe'
  end
end
