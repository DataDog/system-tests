class DatadogController < ApplicationController
    def fork_and_crash
        pid = Process.fork do
            Process.kill('SEGV', Process.pid)
        end

        Process.wait(pid)
    end

    def child_pids
        current_pid = Process.pid

        # Get the child processes
        ps_command = "ps --ppid #{current_pid} --no-headers"

        begin
          # Capture the output of the ps command
          child_processes = `#{ps_command}`
          render plain: child_processes
        rescue => e
          # Handle any potential errors that might occur when executing the command
          render plain: "Error executing command: #{e.message}", status: 500
        end
    end
  end