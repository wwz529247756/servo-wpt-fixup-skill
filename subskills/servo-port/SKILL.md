---
name: servo-port
description: Port a web-platform feature from Firefox (mozilla/gecko-dev) into Servo. Use when implementing a missing CSS property or Web API in Servo and you need to find the reference implementation in Firefox and map it to the Servo (and stylo) code.
---

# Port from Firefox to Servo

Firefox (gecko-dev) is the ground-truth reference for Servo. The checkout is
`<workspace>/gecko-dev` (a required workspace member; see the skill's
`SKILL.md`) with the relevant trees — `dom/animation` +
`servo/components/style`; add trees with `git sparse-checkout add <path>`.

## Where to look

- **Web Animations API / DOM glue:** `gecko-dev/dom/animation/*` (C++).
- **CSS properties + animation model:** `gecko-dev/servo/components/style/*`
  — this is the *same style-crate lineage* as Servo's `stylo`.

## Porting convention

1. Gecko code is annotated with the spec's numbered steps
   (`// Step 1. … // Step 2. …`). Servo's DOM code uses the same convention,
   so the port is mechanical: map spec step → Gecko function → Servo `fn`.
2. Servo is Rust, Gecko DOM is C++ — port the **algorithm/state machine**, not
   the boilerplate.
3. Record the mapping in `<workspace>/PORTING.md` (the workspace porting
   database; spec § → Gecko file/function → Servo file/function).

## Known divergence

`style::animation` lives at `style/animation.rs` in Gecko but at
`style/servo/animation.rs` in the Servo `stylo` fork (same types, different
path). Resolve by **type/module name**, not by path.

## Repos to edit

- **Servo** (`components/script/dom/**`, `components/script_bindings/webidls/*`)
  — DOM interfaces, WebIDL, and the animation tick (`document/animation_manager.rs`).
- **stylo** (`servo/stylo`, a git dependency) — CSS property parsing + the
  `style::animation` model. Bump the rev in `Cargo.toml`, or use a local
  `[patch."https://github.com/servo/stylo"]` checkout.
