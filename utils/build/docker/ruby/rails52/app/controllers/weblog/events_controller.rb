module Sqreen
  module Weblog
    class EventsController < ApplicationController
      protect_from_forgery except: :track

      def new; end

      def track
        name = params[:name]

        render :plain => "#{name} tracked"
      end
    end
  end
end
