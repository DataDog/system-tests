module Sqreen
  module Weblog
    class FilesController < ApplicationController
      def show
        path = "public/#{params[:id]}"
        path += ".#{params[:format]}" if params.key?(:format)

        if params[:way] == 'file_read'
          send_data(File.read(path))
        else
          send_data(open(path).read)
        end
      end
    end
  end
end
