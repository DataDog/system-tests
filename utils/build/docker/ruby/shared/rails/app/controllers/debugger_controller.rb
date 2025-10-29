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
  # Padding
  # Padding

  def expression
    inputValue = params[:inputValue]
    testStruct = ExpressionTestStruct.new
    localValue = inputValue.length
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

  def expression_operators
    intValue = params[:intValue]
    floatValue = params[:floatValue]
    strValue = params[:strValue]
    pii = Pii.new

    render inline: "Int value #{intValue}. Float value #{floatValue}. String value is #{strValue}."
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

  def expression_strings
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

  def expression_collections
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

  def expression_null
  end
end
