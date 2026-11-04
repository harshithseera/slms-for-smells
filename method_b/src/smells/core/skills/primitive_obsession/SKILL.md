---
name: primitive-obsession
smell: primitive_obsession
family: code
status: judged
version: 1
---
<!-- Gate: a parameter annotated str/int/float whose name is a domain concept (email, phone,
     currency, iban, postcode, zip, url, isbn, sku) and that is compared, passed on, or has
     methods called on it in the body. -->
## Smell: primitive_obsession

**Definition.** A domain concept with its own rules (a currency, an email address, money)
is passed around as a raw str, int or float, so its validation and formatting are repeated
wherever it is used.

**Confirm when.**
- must: the function validates, normalises or formats the raw value itself (membership in
  an allowed set, a regex or "@" check, upper/lower/strip, rounding or a currency format).
- any of: the same checks or formatting for that concept appear in another function; two
  related raw values travel together (an amount and its currency).

**Reject when.**
- The value is only stored, looked up as a key, compared for equality or passed through,
  with no rules of its own applied.
- The function is the single, dedicated place that parses or normalises the value at an
  input boundary, and nothing else repeats that work.
- The concept has no rules at all in this codebase.

**Severity.** high: the same validation or formatting is repeated in 2+ functions.
medium: one function carries rules a small value type should own. low: borderline.

**Location:** Class.method or function.

**Fix.** Introduce a small value type (for example a Currency enum or a Money dataclass
with amount and currency) that validates once on creation and formats itself; pass it
instead of the raw values.
