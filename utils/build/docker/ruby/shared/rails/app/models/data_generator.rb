class NestedObject
  attr_accessor :level, :nested

  def initialize(level, nested = nil)
    @level = level
    @nested = nested
  end
end

class ManyFieldsObject
  def initialize(field_count)
    field_count.times do |i|
      instance_variable_set("@field#{i}", i)
    end
  end
end

class DataGenerator
  def self.create_nested_object(max_level, level = 1)
    nested = level < max_level ? create_nested_object(max_level, level + 1) : nil
    NestedObject.new(level, nested)
  end

  def self.generate_test_data(depth, fields, collection_size, string_length)
    # Generate deeply nested object (tests maxReferenceDepth)
    deep_object = depth > 0 ? create_nested_object(depth) : nil

    # Generate object with many fields (tests maxFieldCount)
    many_fields = ManyFieldsObject.new(fields)

    # Generate large collection (tests maxCollectionSize)
    large_collection = []
    collection_size.times do |i|
      large_collection << i
    end

    # Generate long string (tests maxLength)
    long_string = string_length > 0 ? 'A' * string_length : ''

    {
      deepObject: deep_object,
      manyFields: many_fields,
      largeCollection: large_collection,
      longString: long_string
    }
  end
end
