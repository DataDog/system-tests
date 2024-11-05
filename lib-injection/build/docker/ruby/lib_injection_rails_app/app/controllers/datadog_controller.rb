class DatadogController < ApplicationController
    def fork_and_crash
        pid = Process.fork do
            Process.kill('SEGV', Process.pid)
        end

        Process.wait(pid)
    end

    def commandline
        cmdline_content = File.read("/proc/self/cmdline")

        # The command line arguments are separated by null characters, replace them with spaces
        cmdline_readable = cmdline_content.split("\x00").join(" ")

        # Render the command line content as plain text
        render plain: cmdline_readable
    end
  end