# frozen_string_literal: true

module Types
  class QueryType < Types::BaseObject
    field :user, Types::UserType, null: true, description: "Find a user by ID" do
      argument :id, ID, required: true, description: "ID of the user to find"
    end

    def user(id:)
      User.find(id)
    end

    field :userByName, Types::UserType, null: true, description: "Find a user by name" do
      argument :name, String, required: true, description: "Name of the user to find"
    end

    def userByName(name:)
      User.find_by(name: name)
    end

    field :with_error, ID, null: true, description: "Raise an error"

    def with_error
      raise 'test error'
    end
  end
end
