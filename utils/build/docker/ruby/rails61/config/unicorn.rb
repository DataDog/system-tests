after_worker_ready do |server,worker|
  puts "after_worker_ready start"
  req = Rack::MockRequest.new server.app
  req.get('/')
  puts "after_worker_ready end"
end
