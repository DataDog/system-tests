# Padding
# Padding
# Padding
# Padding

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
end
