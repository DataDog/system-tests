class DatadogController < ApplicationController
    def fork_and_crash
        fork do
            Process.kill('SEGV', Process.pid)
        end
    end
  end