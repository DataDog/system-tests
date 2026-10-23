import Lean
import Review
open Lean PR423 GoReview

def main : IO Unit := do
  let stdout ← IO.getStdout
  for (modeName, mode) in [("disabled", Mode.disabled), ("immediate", Mode.immediate),
      ("future_experiments_only", Mode.future)] do
    for (attributeName, attr) in [("absent", Attribute.absent), ("valid", Attribute.valid),
        ("invalid", Attribute.invalid)] do
      let error := match resolveReady mode attr false with
        | .invalidContext => "INVALID_CONTEXT"
        | .flagNotFound => "FLAG_NOT_FOUND"
        | .evaluate => "NONE"
      stdout.putStrLn ((Json.mkObj [("mode", toJson modeName), ("attribute", toJson attributeName),
        ("error", toJson error)]).compress)
