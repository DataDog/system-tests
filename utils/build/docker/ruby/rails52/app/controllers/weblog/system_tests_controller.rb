class Weblog::SystemTestsController < ApplicationController
  def root
    @output = 'OK'
    render 'output'
  end

  def evali
    q = params[:q] || 'secret'
    strategy = params[:strategy] || 'kernel_eval'

    klass = Class.new do
      def self.secret
        'hunter2'
      end

      def secret
        self.secret
      end
    end
    secret = klass.secret

    @output = case strategy
              when 'kernel_eval'
                Kernel.eval(q)
              when 'eval'
                eval(q)
              when 'instance_eval'
                klass.new.instance_eval(q)
              when 'class_eval'
                klass.class_eval(q)
              when 'module_eval'
                klass.module_eval(q)
              end

    render 'output'
  end

  def graphql
    raise ActionController::RoutingError, 'not implemented: graphql'
  end

  def lfi
    q = params[:q] || 'public/robots.txt'
    q = q + '.' + params[:format] if params.key?(:format)

    strategy = params[:strategy] || 'open_string'
    @output = case strategy
              when 'read_string'
                File.read(q)
              when 'open_string'
                File.open(q) { |f| f.read }
              when 'read_pathname'
                File.read(Pathname.new(q))
              when 'open_pathname'
                File.open(Pathname.new(q)) { |f| f.read }
              end
    render 'output', formats: :html
  end

  def mongo
    raise NotImplementedError unless defined?(Mongoid)

    klass = Class.new do
      include Mongoid::Document
      field :title, type: String
      field :text, type: String
      field :role, type: String

      # After initialization, set default values
      after_initialize :set_default_values

      def set_default_values
        # Only set if time_zone IS NOT set
        self.role ||= 'user'
      end
    end

    data = klass.where(title: params[:name])
    @output = JSON.dump(data)
  end

  def shellshock
    raise ActionController::RoutingError, 'not implemented: shellshock'

    command = params[:command]
    env = ENV.to_h.merge({})

    # TODO: handle all shellshock strategies
    strategy = params[:strategy] || 'system'
    @output = case strategy
              when 'popen'
                IO.popen(env, command, &:read)
              when 'exec'
                exec(env, command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'kernel_exec'
                Kernel.exec(env, command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'process_exec'
                Process.exec(env, command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = spawn(env, command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'kernel_spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = Kernel.spawn(env, command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'process_spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = Process.spawn(env, command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'system'
                r, w = IO.pipe
                system(env, command, out: w)
                w.close
                r.read
              when 'kernel_system'
                r, w = IO.pipe
                Kernel.system(env, command, out: w)
                w.close
                r.read
              when 'backticks'
                `#{command}` # might be vulnerable through ENV manipulation?
              when 'kernel_backticks'
                Kernel.send(:`, command) # might be vulnerable through ENV manipulation?
              when 'open'
                open("|#{command}", &:read) # rubocop:disable Security/Open
              when 'kernel_open'
                Kernel.open("|#{command}", &:read) # might be vulnerable through ENV manipulation?
              end

    render 'output'
  end

  def ping
    host = params[:q] || '127.0.0.1'
    strategy = params[:strategy] || 'backticks'

    opt = case RUBY_PLATFORM
          when /darwin/
            '-t'
          else
            '-c'
          end
    command = "ping #{opt} 1 #{host}"

    # TODO: also test with positional optional first arg for env
    # other variants with argv are immune to shi (both string shi via
    # interpolation of param and magic param array to arg array shi via
    # args << foo[])
    @output = case strategy
              when 'popen'
                IO.popen(command, &:read)
              when 'exec'
                exec(command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'kernel_exec'
                Kernel.exec(command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'process_exec'
                Process.exec(command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = spawn(command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'kernel_spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = Kernel.spawn(command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'process_spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = Process.spawn(command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'system'
                r, w = IO.pipe
                system(command, out: w)
                w.close
                r.read
              when 'kernel_system'
                r, w = IO.pipe
                Kernel.system(command, out: w)
                w.close
                r.read
              when 'backticks'
                `#{command}`
              when 'kernel_backticks'
                Kernel.send(:`, command) # send is just not to break some Ruby parsers and coloring
              when 'open'
                open("|#{command}", &:read) # rubocop:disable Security/Open
              when 'kernel_open'
                Kernel.open("|#{command}", &:read)
              end

    render 'output'
  end

  def ssrf
    raise ActionController::RoutingError, 'not implemented: ssrf'
  end

  def su
    user_id = params[:id]

    @output = user_id

    render 'output'
  end

  def webshell
    command = params[:command]

    strategy = params[:strategy] || 'backticks'
    @output = case strategy
              when 'popen'
                IO.popen(command, &:read)
              when 'exec'
                exec(command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'kernel_exec'
                Kernel.exec(command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'process_exec'
                Process.exec(command, &:read) # will replace process and quit server, unless attack is blocked!
              when 'spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = spawn(command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'kernel_spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = Kernel.spawn(command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'process_spawn'
                r, w = IO.pipe
                Thread.new do
                  pid = Process.spawn(command, out: w)
                  Process.wait(pid)
                end
                w.close
                r.read
              when 'system'
                r, w = IO.pipe
                system(command, out: w)
                w.close
                r.read
              when 'kernel_system'
                r, w = IO.pipe
                Kernel.system(command, out: w)
                w.close
                r.read
              when 'backticks'
                `#{command}`
              when 'kernel_backticks'
                Kernel.send(:`, command) # send is just not to break some Ruby parsers and coloring
              when 'open'
                open("|#{command}", &:read) # rubocop:disable Security/Open
              when 'kernel_open'
                Kernel.open("|#{command}", &:read)
              end

    render 'output'
  end

  def xss
    @output = params[:q].to_s.html_safe

    case params[:strategy] || 'erb'
    when 'erb'
      render 'output'
    when 'slim'
      raise ActionController::RoutingError, 'not implemented: slim'
    when 'haml'
      raise ActionController::RoutingError, 'not implemented: haml'
    when 'haml4'
      raise ActionController::RoutingError, 'not implemented: haml4'
    end
  end

  def sqli
    @output = Foo.find_by_sql("SELECT * FROM foos WHERE id=#{params[:id]}").first

    render 'output'
  end

  def xxe
    raise ActionController::RoutingError, 'not implemented: xxe'
  end
end
