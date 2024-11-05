class DatadogController < ApplicationController
    def fork_and_crash
        pid = Process.fork do
            Process.kill('SEGV', Process.pid)
        end

        Process.wait(pid)
    end
  end