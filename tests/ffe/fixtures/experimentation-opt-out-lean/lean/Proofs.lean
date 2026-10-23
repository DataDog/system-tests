import Contract

namespace PR423

theorem disabled_preserves_evaluation (a : Attribute) (t : Activation) (logging : Bool) :
    policy .disabled a t logging = normal := by cases a <;> rfl

theorem absent_preserves_evaluation (m : Mode) (t : Activation) (logging : Bool) :
    policy m .absent t logging = normal := by cases m <;> rfl

theorem invalid_context_precedes_activation (m : Mode) (t : Activation) (logging : Bool)
    (enabled : m ≠ .disabled) :
    policy m .invalid t logging = ⟨.invalidContext, false⟩ := by
  cases m <;> simp_all [policy]

theorem immediate_ignores_activation (t : Activation) (logging : Bool) :
    policy .immediate .valid t logging = ⟨.none, logging⟩ := by rfl

theorem invalid_activation_fails_future_flag_even_without_logging (logging : Bool) :
    policy .future .valid .invalid logging = ⟨.parseError, false⟩ := by rfl

theorem only_future_cutoff_needs_activation (m : Mode) (a : Attribute)
    (t : Activation) (logging : Bool) :
    (policy m a t logging).error = .parseError ↔
      m = .future ∧ a = .valid ∧ t = .invalid := by
  cases m <;> cases a <;> cases t <;> simp [policy, normal]

theorem before_cutoff_retains_experiment (logging : Bool) :
    policy .future .valid .before logging = normal := by rfl

theorem equality_excludes_experiment :
    policy .future .valid .equal true = ⟨.none, true⟩ := by rfl

theorem missing_excludes_experiment :
    policy .future .valid .missing true = ⟨.none, true⟩ := by rfl

theorem ordinary_allocation_never_excluded (m : Mode) (a : Attribute) (t : Activation) :
    (policy m a t false).exclude = false := by
  cases m <;> cases a <;> cases t <;> rfl

theorem disabled_never_remaps_error (a : Attribute) (e : Error) :
    pending .disabled a e = e := by cases a <;> cases e <;> rfl

theorem malformed_context_never_remaps_error (m : Mode) (e : Error) :
    pending m .invalid e = e := by cases m <;> cases e <;> rfl

theorem parse_error_is_preserved (m : Mode) (a : Attribute) :
    pending m a .parseError = .parseError := by
  cases m <;> cases a <;> rfl

theorem enabled_valid_context_is_not_invalid (m : Mode) (a : Attribute)
    (enabled : m ≠ .disabled) (valid : a ≠ .invalid) :
    pending m a .invalidContext = .providerNotReady := by
  cases m <;> cases a
  all_goals first | exact (enabled rfl).elim | exact (valid rfl).elim | rfl

theorem truncation_at_most_nine_digits (xs : List Char) :
    (firstNanos xs).length ≤ 9 := by
  simp [firstNanos, List.length_take, Nat.min_le_left]

theorem truncation_is_idempotent (xs : List Char) :
    firstNanos (firstNanos xs) = firstNanos xs := by
  simp [firstNanos, List.take_take]

theorem subnanosecond_digits_do_not_round (xs : List Char) :
    fractionNanos (firstNanos xs) = fractionNanos xs := by
  simp only [fractionNanos, truncation_is_idempotent]

theorem absent_fraction_is_zero : fractionNanos [] = 0 := by rfl

theorem unix_epoch_is_zero : utcSeconds 1970 1 1 0 0 0 0 = 0 := by decide

theorem first_supported_instant : utcSeconds 0 1 1 0 0 0 0 = -62167219200 := by decide

theorem last_supported_second :
    utcSeconds 9999 12 31 23 59 59 0 = 253402300799 := by decide

theorem absent_request_omits_options (m : Mode) :
    request m .absent = ⟨true, false, .none⟩ := by cases m <;> rfl

theorem disabled_request_ignores_attribute (a : Attribute) :
    request .disabled a = ⟨true, false, .none⟩ := by cases a <;> rfl

theorem invalid_enabled_request_is_not_sent (m : Mode) (enabled : m ≠ .disabled) :
    request m .invalid = ⟨false, false, .invalidContext⟩ := by
  cases m <;> simp_all [request]

theorem no_policy_rejects_filtered_boolean (mode : AckMode) (cutoff : AckCutoff) :
    acknowledges .none .yes mode cutoff = false := by cases mode <;> rfl

theorem no_policy_rejects_filtered_mode (ack : AckBoolean) (mode : AckMode)
    (cutoff : AckCutoff) (filtered : mode ≠ .missing) :
    acknowledges .none ack mode cutoff = false := by
  cases ack <;> cases mode
  all_goals first | exact (filtered rfl).elim | rfl

theorem ordinary_unmarked_response_accepted (cutoff : AckCutoff) :
    acknowledges .none .missing .missing cutoff = true := by rfl

theorem immediate_legacy_acknowledgement_accepted (cutoff : AckCutoff) :
    acknowledges .immediate .yes .missing cutoff = true := by rfl

theorem future_requires_mode_and_matching_instant (ack : AckBoolean) (mode : AckMode)
    (cutoff : AckCutoff) :
    acknowledges .future ack mode cutoff = true ↔
      mode = .future ∧ (cutoff = .equal ∨ cutoff = .equivalent) := by
  cases ack <;> cases mode <;> cases cutoff <;> simp [acknowledges]

theorem boolean_alone_is_insufficient_for_future (cutoff : AckCutoff) :
    acknowledges .future .yes .missing cutoff = false := by cases cutoff <;> rfl

#print axioms no_policy_rejects_filtered_boolean
#print axioms no_policy_rejects_filtered_mode
#print axioms ordinary_unmarked_response_accepted
#print axioms immediate_legacy_acknowledgement_accepted
#print axioms future_requires_mode_and_matching_instant
#print axioms boolean_alone_is_insufficient_for_future
#print axioms absent_request_omits_options
#print axioms disabled_request_ignores_attribute
#print axioms invalid_enabled_request_is_not_sent
#print axioms only_future_cutoff_needs_activation
#print axioms enabled_valid_context_is_not_invalid
#print axioms truncation_is_idempotent
#print axioms subnanosecond_digits_do_not_round
#print axioms last_supported_second

end PR423
