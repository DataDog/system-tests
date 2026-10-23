import Std

namespace PR423

/-- Strict is the historical a96b572 policy; proposal is final JS 38d611c behavior.
    Neither constructor asserts fleet approval. -/
inductive Profile where
  | strict | proposal
  deriving BEq, DecidableEq, Repr

structure Instant where
  seconds : Int
  nanos : Nat
  deriving BEq, DecidableEq, Repr

def asciiDigit (c : Char) : Bool := '0' ≤ c && c ≤ '9'
def decimal (chars : List Char) : Nat :=
  chars.foldl (fun n c => n * 10 + (c.toNat - '0'.toNat)) 0

def firstNanos (fraction : List Char) : List Char := fraction.take 9

def fractionNanos (fraction : List Char) : Nat :=
  let kept := firstNanos fraction
  decimal kept * 10 ^ (9 - kept.length)

def field (chars : List Char) (start width : Nat) : Option Nat := do
  let digits := (chars.drop start).take width
  if digits.length != width || !digits.all asciiDigit then none
  else some (decimal digits)

def charAt (chars : List Char) (index : Nat) : Char := chars[index]?.getD '\x00'

def leap (year : Nat) : Bool := year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)

def daysInMonth (year month : Nat) : Nat :=
  if month == 2 then if leap year then 29 else 28
  else if month == 4 || month == 6 || month == 9 || month == 11 then 30 else 31

/-- Proleptic Gregorian arithmetic includes leap year zero. -/
def daysBeforeYear (year : Nat) : Nat :=
  365 * year + (year + 3) / 4 - (year + 99) / 100 + (year + 399) / 400

def daysBeforeMonth (year month : Nat) : Nat :=
  ((List.range (month - 1)).map (fun i => daysInMonth year (i + 1))).foldl (· + ·) 0

def utcSeconds (year month day hour minute second : Nat) (offset : Int) : Int :=
  ((Int.ofNat (daysBeforeYear year + daysBeforeMonth year month + day - 1) - 719528) * 86400)
    + Int.ofNat (hour * 3600 + minute * 60 + second) - offset

def parseOffset (profile : Profile) (zone : List Char) : Option Int := do
  if zone == ['Z'] || (profile == .proposal && zone == ['z']) then return 0
  if zone.length != 6 || (charAt zone 0 != '+' && charAt zone 0 != '-') || charAt zone 3 != ':' then none
  else do
    let hours ← field zone 1 2
    let minutes ← field zone 4 2
    if hours > 23 || minutes > 59 then none
    else
      let seconds := Int.ofNat (hours * 3600 + minutes * 60)
      some (if charAt zone 0 == '-' then -seconds else seconds)

/-- The grammar is explicit: ASCII digits, full fields, exact separators and no whitespace.
    Epoch seconds are calculated without a host date parser. -/
def parseTimestamp (profile : Profile) (input : String) : Option Instant := do
  let chars := input.toList
  if chars.length < 20 || charAt chars 4 != '-' || charAt chars 7 != '-' ||
      (charAt chars 10 != 'T' && !(profile == .proposal && charAt chars 10 == 't')) ||
      charAt chars 13 != ':' || charAt chars 16 != ':' then none
  else do
    let year ← field chars 0 4
    let month ← field chars 5 2
    let day ← field chars 8 2
    let hour ← field chars 11 2
    let minute ← field chars 14 2
    let second ← field chars 17 2
    if month < 1 || month > 12 || day < 1 || day > daysInMonth year month ||
        hour > 23 || minute > 59 || second > 59 then none
    else do
      let suffix := chars.drop 19
      let (fraction, zone) ← if charAt suffix 0 == '.' then do
        let digits := (suffix.drop 1).takeWhile asciiDigit
        if digits.isEmpty || (profile == .strict && digits.length > 9) then none
        else some (digits, (suffix.drop 1).drop digits.length)
      else some ([], suffix)
      let offset ← parseOffset profile zone
      let seconds := utcSeconds year month day hour minute second offset
      if seconds < -62167219200 || seconds > 253402300799 then none
      else some { seconds, nanos := fractionNanos fraction }

inductive Mode where
  | disabled | immediate | future
  deriving BEq, DecidableEq, Repr
inductive Attribute where
  | absent | valid | invalid
  deriving BEq, DecidableEq, Repr
inductive Activation where
  | missing | invalid | before | equal | after
  deriving BEq, DecidableEq, Repr
inductive Error where
  | none | invalidContext | parseError | providerNotReady
  deriving BEq, DecidableEq, Repr
structure PolicyResult where
  error : Error
  exclude : Bool
  deriving BEq, DecidableEq, Repr

def normal : PolicyResult := ⟨.none, false⟩

/-- Activation is the flag's relevant validity/boundary state. Invalid metadata may be
    on an unreachable allocation: future mode validates the affected flag up front. -/
def policy (mode : Mode) (attr : Attribute) (activation : Activation)
    (doLog : Bool) : PolicyResult :=
  match mode, attr with
  | .disabled, _ => normal
  | _, .absent => normal
  | _, .invalid => ⟨.invalidContext, false⟩
  | .immediate, .valid => ⟨.none, doLog⟩
  | .future, .valid =>
    match activation with
    | .invalid => ⟨.parseError, false⟩
    | .before => normal
    | .missing | .equal | .after => ⟨.none, doLog⟩

/-- Browser online-provider error remapping. Provider status is a separate concern. -/
def pending (mode : Mode) (attr : Attribute) (coreError : Error) : Error :=
  if mode != .disabled && attr != .invalid && coreError == .invalidContext
  then .providerNotReady else coreError

structure RequestResult where
  send : Bool
  options : Bool
  error : Error
  deriving BEq, DecidableEq, Repr

/-- Fetch validation uses the effective subject policy: an enabled mode alone does
    not add evaluation_options when the attribute is absent. -/
def request (mode : Mode) (attr : Attribute) : RequestResult :=
  match mode, attr with
  | .disabled, _ => ⟨true, false, .none⟩
  | _, .absent => ⟨true, false, .none⟩
  | _, .invalid => ⟨false, false, .invalidContext⟩
  | _, .valid => ⟨true, true, .none⟩

inductive AckPolicy where
  | none | immediate | future
  deriving BEq, DecidableEq, Repr
inductive AckBoolean where
  | missing | no | yes
  deriving BEq, DecidableEq, Repr
inductive AckMode where
  | missing | immediate | future
  deriving BEq, DecidableEq, Repr
inductive AckCutoff where
  | missing | equal | equivalent | different | invalid
  deriving BEq, DecidableEq, Repr

/-- The response acknowledgement helper's well-typed metadata domain. The policy is
    effective: an enabled mode with an absent subject attribute still has policy none.
    Equivalent cutoff means the same normalized instant, including timezone spelling. -/
def acknowledges (effective : AckPolicy) (ack : AckBoolean) (mode : AckMode)
    (cutoff : AckCutoff) : Bool :=
  match effective with
  | .none => match ack, mode with
    | .yes, _ => false
    | _, .missing => true
    | _, _ => false
  | .immediate => match ack, mode with
    | .yes, .missing | .yes, .immediate => true
    | _, _ => false
  | .future => match mode, cutoff with
    | .future, .equal | .future, .equivalent => true
    | _, _ => false

end PR423
