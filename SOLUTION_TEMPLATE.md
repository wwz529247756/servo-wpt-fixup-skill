---
fixture:  <path, e.g. web-animations/timing-model/animations/updating-the-finished-state.html>
spec:     <shortname, e.g. web-animations-1>
category: webapi
status:   pending | diagnosed | in-progress | fixed | verified | blocked
---

# Solution: <fixture>

## 1. Fixture
- **Path:** `<path>`
- **Test type:** testharness | reftest | wdspec | crashtest
- **What it asserts:** (summary from reading the test)

## 2. W3C spec reference
- **Spec:** [Title](url)
- **Section:** §x.y — <heading>
- **Normative text / algorithm:** (from the spec dictionary + link)
- **Term / property / interface involved:** ...

## 3. Firefox reference
- **File(s):** `gecko-dev/...`
- **Function / algorithm:** (e.g. `Animation::Play`)
- **How Firefox does it:** (step summary or short excerpt)

## 4. Diagnosis (root cause)
- Missing API method / property not parsed / event ordering / rendering diff.

## 5. Implementation plan
- **Repo:** servo | stylo
- **Files to change:** ...
- **Steps:**
  1. ...
  2. ...
- **Algorithm sketch:** (spec steps / pseudo-code)

## 6. Verification
- **Command:** `mach test-wpt --release <path>`
- **Expected:** pass
- **Gate suites:** ...

## 7. Result & notes
- Outcome, regression notes, expectation changes, follow-ups.
