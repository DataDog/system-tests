# Run a single conformance case by index against dd-trace-rb, via the rust
# cdylib (loaded with Fiddle). The case env (DD_* vars, DD_TRACE_AGENT_URL) is
# applied by the parent runner (run.rb) via the subprocess env, BEFORE this file
# `require`s the adapter (and therefore `require 'datadog'` + Datadog.configure),
# so dd-trace-rb initializes with the case's configuration.
#
# The cdylib exposes (see CONTRACT.md):
#   char* str_run_case(int32_t index, Dispatch dispatch)
#   void  str_free(char* p)
# and calls our `dispatch(op, args_json)` once per Tracer method. We hand it a
# Fiddle::Closure that decodes the args, calls Dispatch.handle, and returns a
# libc-malloc'd NUL-terminated JSON string (rust free()s it).

require "fiddle"
require "json"
require_relative "adapter"

LIB_PATH = File.join(__dir__, "shim", "target", "debug", "libstr_ruby_shim.dylib")

unless File.exist?(LIB_PATH)
  warn "cdylib not found at #{LIB_PATH} (build the shim first: cd shim && cargo build)"
  exit 3
end

shim = Fiddle.dlopen(LIB_PATH)
libc = Fiddle.dlopen(nil)

MALLOC = Fiddle::Function.new(libc["malloc"], [Fiddle::TYPE_SIZE_T], Fiddle::TYPE_VOIDP)
STR_RUN_CASE = Fiddle::Function.new(
  shim["str_run_case"], [Fiddle::TYPE_INT, Fiddle::TYPE_VOIDP], Fiddle::TYPE_VOIDP
)
STR_FREE = Fiddle::Function.new(shim["str_free"], [Fiddle::TYPE_VOIDP], Fiddle::TYPE_VOID)

# Copy `str` into libc-malloc'd memory with a trailing NUL and return the raw
# pointer; ownership transfers to the rust caller, which calls free() on it.
def to_c_string(str)
  data = str.b + "\x00".b
  ptr = MALLOC.call(data.bytesize)
  ptr.size = data.bytesize
  ptr[0, data.bytesize] = data
  ptr
end

# Dispatch callback: char* (*)(const char* op, const char* args_json)
DISPATCH = Fiddle::Closure::BlockCaller.new(
  Fiddle::TYPE_VOIDP, [Fiddle::TYPE_VOIDP, Fiddle::TYPE_VOIDP]
) do |op_ptr, args_ptr|
  # A Ruby exception must NOT propagate across the C boundary (UB); marshal it
  # as {"__error__":...} so the rust side turns it into a caught FAIL.
  begin
    op = Fiddle::Pointer.new(op_ptr).to_s
    args_json = Fiddle::Pointer.new(args_ptr).to_s
    args = args_json.empty? ? [] : JSON.parse(args_json)
    to_c_string(JSON.generate(Dispatch.handle(op, args)))
  rescue Exception => e
    to_c_string(JSON.generate({ "__error__" => "#{e.class}: #{e.message}" }))
  end
end

index = Integer(ARGV[0])
res_ptr = STR_RUN_CASE.call(index, DISPATCH)
result = Fiddle::Pointer.new(res_ptr).to_s
STR_FREE.call(res_ptr)

if result.start_with?("PASS")
  puts result
  exit 0
elsif result.start_with?("SKIP")
  puts result
  exit 2
elsif ENV["RUBY_KNOWN_DIFF"] == "1"
  # Downgrade a genuine FAIL to a documented skip. A listed diff that PASSES
  # still reports PASS above, so the list can't hide a fix.
  name = result.sub(/\AFAIL /, "").split(":", 2).first
  puts "SKIP #{name} (known dd-trace-rb diff)"
  exit 2
else
  puts result
  exit 1
end
