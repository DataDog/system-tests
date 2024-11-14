class DatadogController < ApplicationController
    def fork_and_crash
        pid = Process.fork do
            Process.kill('SEGV', Process.pid)
        end

        Process.wait(pid)
    end

    def child_pids
      current_pid = Process.pid
      child_pids = []

      begin
        # Iterate over all the directories in /proc
        Dir.foreach('/proc') do |pid|
          # Skip non-numeric directories
          next unless pid =~ /^\d+$/

          status_path = "/proc/#{pid}/status"

          # Read the status file for each process
          if File.exist?(status_path)
            File.open(status_path) do |file|
              file.each_line do |line|
                if line.start_with?("PPid:")
                  ppid = line.split[1].to_i
                  if ppid == current_pid
                    child_pids << pid
                  end
                  break
                end
              end
            end
          end
        end

        # Render the response with the list of child PIDs
        render plain: "#{child_pids.join(', ')}"
      rescue => e
        # Handle any errors that might occur during reading from /proc
        render plain: "Error: #{e.message}", status: 500
      end
    end
  end