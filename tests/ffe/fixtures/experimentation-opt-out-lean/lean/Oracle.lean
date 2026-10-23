import Lean
import Contract

open Lean PR423

namespace Oracle

def readMode (j : Json) : Except String Mode := do
  match ← j.getObjValAs? String "mode" with
  | "disabled" => return .disabled
  | "immediate" => return .immediate
  | "future_experiments_only" => return .future
  | other => throw s!"Unknown mode: {other}"

def readAttribute (j : Json) : Except String Attribute := do
  match ← j.getObjValAs? String "attribute" with
  | "absent" => return .absent
  | "valid" => return .valid
  | "invalid" => return .invalid
  | other => throw s!"Unknown attribute state: {other}"

def readActivation (j : Json) : Except String Activation := do
  match ← j.getObjValAs? String "activation" with
  | "missing" => return .missing
  | "invalid" => return .invalid
  | "before" => return .before
  | "equal" => return .equal
  | "after" => return .after
  | other => throw s!"Unknown activation state: {other}"

def readError (j : Json) : Except String PR423.Error := do
  match ← j.getObjValAs? String "coreError" with
  | "NONE" => return .none
  | "INVALID_CONTEXT" => return .invalidContext
  | "PARSE_ERROR" => return .parseError
  | "PROVIDER_NOT_READY" => return .providerNotReady
  | other => throw s!"Unknown core error: {other}"

def errorName : PR423.Error → String
  | .none => "NONE"
  | .invalidContext => "INVALID_CONTEXT"
  | .parseError => "PARSE_ERROR"
  | .providerNotReady => "PROVIDER_NOT_READY"

def timestampResult (request : Json) : Except String Json := do
  let profile ← match ← request.getObjValAs? String "profile" with
    | "strict" => pure Profile.strict
    | "proposal" => pure Profile.proposal
    | other => throw s!"Unknown profile: {other}"
  let input ← request.getObjVal? "input"
  let result := input.getStr?.toOption.bind (parseTimestamp profile)
  return match result with
    | none => Json.mkObj [("accepted", toJson false)]
    | some instant => Json.mkObj [("accepted", toJson true),
        ("seconds", toJson instant.seconds), ("nanos", toJson instant.nanos)]

def policyResult (request : Json) : Except String Json := do
  let args ← request.getObjVal? "args"
  let result := policy (← readMode args) (← readAttribute args)
    (← readActivation args) (← args.getObjValAs? Bool "doLog")
  return Json.mkObj [("error", toJson (errorName result.error)), ("exclude", toJson result.exclude)]

def pendingResult (request : Json) : Except String Json := do
  let args ← request.getObjVal? "args"
  let result := pending (← readMode args) (← readAttribute args) (← readError args)
  return Json.mkObj [("error", toJson (errorName result))]

def requestResult (input : Json) : Except String Json := do
  let args ← input.getObjVal? "args"
  let result := PR423.request (← readMode args) (← readAttribute args)
  return Json.mkObj [("send", toJson result.send), ("options", toJson result.options),
    ("error", toJson (errorName result.error))]

def acknowledgementResult (input : Json) : Except String Json := do
  let args ← input.getObjVal? "args"
  let effective ← match ← args.getObjValAs? String "policy" with
    | "none" => pure AckPolicy.none
    | "immediate" => pure AckPolicy.immediate
    | "future" => pure AckPolicy.future
    | other => throw s!"Unknown acknowledgement policy: {other}"
  let ack ← match ← args.getObjValAs? String "acknowledged" with
    | "missing" => pure AckBoolean.missing
    | "false" => pure AckBoolean.no
    | "true" => pure AckBoolean.yes
    | other => throw s!"Unknown acknowledgement boolean state: {other}"
  let mode ← match ← args.getObjValAs? String "mode" with
    | "missing" => pure AckMode.missing
    | "immediate" => pure AckMode.immediate
    | "future" => pure AckMode.future
    | other => throw s!"Unknown acknowledgement mode: {other}"
  let cutoff ← match ← args.getObjValAs? String "cutoff" with
    | "missing" => pure AckCutoff.missing
    | "equal" => pure AckCutoff.equal
    | "equivalent" => pure AckCutoff.equivalent
    | "different" => pure AckCutoff.different
    | "invalid" => pure AckCutoff.invalid
    | other => throw s!"Unknown acknowledgement cutoff: {other}"
  return Json.mkObj [("accepted", toJson (acknowledges effective ack mode cutoff))]

def dispatch (request : Json) : Except String Json := do
  let id ← request.getObjVal? "id"
  let result ← match ← request.getObjValAs? String "kind" with
    | "timestamp" => timestampResult request
    | "policy" => policyResult request
    | "pending" => pendingResult request
    | "request" => requestResult request
    | "ack" => acknowledgementResult request
    | other => throw s!"Unknown request kind: {other}"
  return Json.mkObj [("id", id), ("observed", result)]

end Oracle

def main : IO Unit := do
  let stdin ← IO.getStdin
  let stdout ← IO.getStdout
  repeat
    let line ← stdin.getLine
    if line.isEmpty then break
    let request ← match Json.parse line with
      | .ok value => pure value
      | .error message => throw (IO.userError s!"Invalid JSON request: {message}")
    let response ← match Oracle.dispatch request with
      | .ok value => pure value
      | .error message => throw (IO.userError s!"Invalid oracle request: {message}")
    stdout.putStrLn response.compress
