# IMPORTANT: This file is used as instrumentation target for testing
# dynamic instrumentation. Line numbers specified in the comments must match
# the actual line number of the respective lines or the tests will fail.

class DebuggerController < ActionController::Base
  def init
    # This method does nothing.
    # When the endpoint corresponding to it is invoked however,
    # the middleware installed by dd-trace-rb initializes remote configuration.
    render inline: 'debugger init'
  end

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def log_probe
    render inline: 'Log probe' # This needs to be line 20
  end

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def mix_probe
    value = params[:string_arg].length * Integer(params[:int_arg])
    render inline: "Mixed result #{value}" # must be line 52
  end

  # Padding
  # Padding
  # Padding

  def pii
    pii = Pii.new
    customPii = CustomPii.new
    value = pii.test_value
    custom_value = customPii.test_value
    render inline: "PII #{value}. CustomPII #{custom_value}" # must be line 64
  end

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def expression
    inputValue = params[:inputValue]
    testStruct = ExpressionTestStruct.new
    localValue = inputValue.length

    render inline: "Great success number #{localValue}"
  end # must be line 82

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def expression_operators
    intValue = params[:intValue].to_i
    floatValue = params[:floatValue].to_f
    strValue = params[:strValue]
    pii = Pii.new

    render inline: "Int value #{intValue}. Float value #{floatValue}. String value is #{strValue}."
  end # line 102

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def expression_strings
    strValue = params[:strValue].to_s
    emptyString = params[:emptyString].to_s
    nullString = params[:nullString]

    render inline: "strValue #{strValue}. emptyString #{emptyString}. #{nullString}."
  end # line 122

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def expression_collections
    factory = CollectionFactory.new

    # Types copied from python
    a0 = factory.get_collection(0, "array")
    l0 = factory.get_collection(0, "list")
    h0 = factory.get_collection(0, "hash")
    a1 = factory.get_collection(1, "array")
    l1 = factory.get_collection(1, "list")
    h1 = factory.get_collection(1, "hash")
    a5 = factory.get_collection(5, "array")
    l5 = factory.get_collection(5, "list")
    h5 = factory.get_collection(5, "hash")

    a0_count = a0.length
    l0_count = l0.length
    h0_count = h0.length
    a1_count = a1.length
    l1_count = l1.length
    h1_count = h1.length
    a5_count = a5.length
    l5_count = l5.length
    h5_count = h5.length

    render inline: "#{a0_count},#{a1_count},#{a5_count},#{l0_count},#{l1_count},#{l5_count},#{h0_count},#{h1_count},#{h5_count}."
  end # line 162

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def expression_null
    intValue = params[:intValue]
    strValue = params[:strValue]
    boolValue = params[:boolValue]

    pii = nil
    if boolValue
      pii = Pii.new
    end

    render inline: "Pii is null #{pii.nil?}. intValue is null #{intValue.nil?}. strValue is null #{strValue.nil?}."
  end # line 192

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def expression_exception
    raise "Hello from exception"
  end # line 212

  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding
  # Padding

  def snapshot_limits
    data = DataGenerator.generate_test_data(
      params[:depth].to_i,
      params[:fields].to_i,
      params[:collectionSize].to_i,
      params[:stringLength].to_i
    )
    deepObject = data[:deepObject]
    manyFields = data[:manyFields]
    largeCollection = data[:largeCollection]
    longString = data[:longString]
    render inline: 'Capture limits probe' # must be line 233
  end
end
