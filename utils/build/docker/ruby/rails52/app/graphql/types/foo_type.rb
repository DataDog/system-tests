module Types
  class FooType < Types::BaseObject
    description "foo"
    field :key, String, null: false
    field :value, String, null: false
  end
end
