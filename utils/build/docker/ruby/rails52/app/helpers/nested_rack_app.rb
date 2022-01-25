class NestedRackApp
  def call(env)
    [200, {"Content-Type" => "text/html; charset=utf-8"}, ["Hello World from Rack"]]
  end
end
