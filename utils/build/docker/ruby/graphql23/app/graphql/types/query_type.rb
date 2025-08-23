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

    # Field for testing GraphQL operation variables with all scalar types
    field :withParameters, ID, null: true, description: "Test field for GraphQL operation variables" do
      argument :intParam, Integer, required: false, description: "Integer parameter for testing"
      argument :floatParam, Float, required: false, description: "Float parameter for testing"
      argument :stringParam, String, required: false, description: "String parameter for testing"
      argument :booleanParam, Boolean, required: false, description: "Boolean parameter for testing"
      argument :idParam, ID, required: false, description: "ID parameter for testing"
      argument :customParam, Types::CustomInputType, required: false, description: "Custom input type parameter for testing"
    end

    def withParameters(intParam: nil, floatParam: nil, stringParam: nil, booleanParam: nil, idParam: nil, customParam: nil)
      # This field is used to test GraphQL operation variables capture
      # The arguments are optional so we can test different combinations
      # customParam contains both integer_field and string_field scalars
      raise 'test error'
    end
  end
end
