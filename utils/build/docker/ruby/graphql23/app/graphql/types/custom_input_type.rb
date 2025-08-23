# frozen_string_literal: true

module Types
  class CustomInputType < Types::BaseInputObject
    graphql_name 'CustomInputType'
    description 'An input type containing both an integer and a string'

    argument :integer_field, Integer, required: false, description: 'An integer field'
    argument :string_field, String, required: false, description: 'A string field'
  end
end
