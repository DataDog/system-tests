# frozen_string_literal: true

class SystemTestSchema < GraphQL::Schema
  trace_with SystemTestTracer

  query(Types::QueryType)

  # TODO: Tracing doesn't support the Fiber-based GraphQL::Dataloader yet
  # use GraphQL::Dataloader

  # Stop validating when it encounters this many errors:
  validate_max_errors(100)

  rescue_from(RuntimeError) do |err, obj, args, ctx, field|
    # Custom extension values used for testing.
    raise GraphQL::ExecutionError.new(err.message, extensions: {
      int: 1,
      float: 1.1,
      str: '1',
      bool: true,
      other: [1, 'foo'],
      not_captured: 'nope',
    })
  end

  # Relay-style Object Identification:

  # Return a string UUID for `object`
  def self.id_from_object(object, type_definition, query_ctx)
    # For example, use Rails' GlobalID library (https://github.com/rails/globalid):
    object.to_gid_param
  end

  # Given a string UUID, find the object
  def self.object_from_id(global_id, query_ctx)
    # For example, use Rails' GlobalID library (https://github.com/rails/globalid):
    GlobalID.find(global_id)
  end
end
