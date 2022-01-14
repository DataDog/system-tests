class QueryType < GraphQL::Schema::Object
  description "The query root of this schema"

  # First describe the field signature:
  field :foo, Types::FooType, null: true do
    description "Find a foo"
    argument :key, String, required: true
    argument :value, String, required: false
  end

  # Then provide an implementation:
  def foo(key:, value: nil)
    Foo.find_by(key: key)
  end

  # First describe the field signature:
  field :foos, [Types::FooType], null: false do
    description "Find a foo"
    argument :key, String, required: true
    argument :value, String, required: false
  end

  def foos(key:, value: nil)
    Foo.where("key = #{key}")
  end
end
