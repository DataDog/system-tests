class DatadogController < ApplicationController
  def crash
    Process.kill('SEGV', Process.pid)
  end
end
