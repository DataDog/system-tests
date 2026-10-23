import Contract

namespace GoReview
open PR423

/-- D015 proposal: provider disablement precedes optional mode validation.
    This is a proposed ordering, not an observation of the Go constructor. -/
inductive Construction where
  | noop | start | invalidMode
  deriving DecidableEq, Repr

def construct (providerEnabled modeValid : Bool) : Construction :=
  if !providerEnabled then .noop else if modeValid then .start else .invalidMode

theorem disabled_provider_wins (valid : Bool) : construct false valid = .noop := by
  cases valid <;> rfl

theorem enabled_invalid_mode_rejects : construct true false = .invalidMode := by rfl

/-- D016 observed ordering only after provider readiness and targeting-key checks.
    Flag lookup errors include FLAG_NOT_FOUND; earlier errors are outside this model. -/
inductive Resolution where
  | evaluate | invalidContext | flagNotFound
  deriving DecidableEq, Repr

def resolveReady (m : Mode) (a : Attribute) (flagExists : Bool) : Resolution :=
  if m != .disabled && a == .invalid then .invalidContext
  else if flagExists then .evaluate else .flagNotFound

theorem invalid_context_precedes_lookup (m : Mode) (flagExists : Bool)
    (enabled : m ≠ .disabled) : resolveReady m .invalid flagExists = .invalidContext := by
  cases m
  case disabled => exact (enabled rfl).elim
  case immediate => rfl
  case future => rfl

theorem disabled_ignores_invalid_attribute (flagExists : Bool) :
    resolveReady .disabled .invalid flagExists = resolveReady .disabled .absent flagExists := by rfl

/-- Reviewer alternative for D004: invalid activation becomes missing.
    The browser proposal retains invalid and missing as distinct states. -/
def invalidAsMissing (m : Mode) (a : Attribute) (activation : Activation)
    (logging : Bool) : PolicyResult :=
  policy m a (if activation == .invalid then .missing else activation) logging

theorem activation_alternatives_disagree :
    policy .future .valid .invalid true ≠ invalidAsMissing .future .valid .invalid true := by
  decide

/-- Directly records the case conflict: global quarantine cannot preserve disabled mode. -/
theorem disabled_invalid_activation_is_not_parse_error :
    (policy .disabled .valid .invalid true).error ≠ .parseError := by decide

#print axioms disabled_provider_wins
#print axioms enabled_invalid_mode_rejects
#print axioms invalid_context_precedes_lookup
#print axioms disabled_ignores_invalid_attribute
#print axioms activation_alternatives_disagree
#print axioms disabled_invalid_activation_is_not_parse_error
end GoReview
