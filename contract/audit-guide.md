# Shortcut Audit Guide

Use `shortcut-schema.json` as the executable contract and `shortcut-vocabulary.md` as its
generated reference. This guide defines how to apply them.

## Independent Axes

- `auditStatus` measures the completeness of the audit, not runtime confidence.
- `role` identifies the preferred solution, a current fallback, or another candidate.
- `implementationType` identifies the technical work required.
- `mappingClass` describes semantic fidelity.
- `availability` describes the underlying capability, not whether a key is bound.
- `status` is the implementation lifecycle state.
- Each evidence `result` applies only to that evidence claim.

`Assessed` does not mean runtime verified. `Preferred` does not mean implemented. A `(new)`
action target does not exist; evidence for it must use `Building block exists`, not `Target exists`.

## Evidence

- Use `Confirmed` only for a direct binding, manual test, E2E test, or the narrow fact of a
  registered existing target.
- Use `Candidate` for source-based behavioral conclusions that have not been exercised.
- A `Missing` capability requires a `Capability audit` with `Capability missing`; record search
  scope, search terms, and the relevant subsystems.
- Record every proposed-key collision, including a collision with the current fallback.
- Prefer `../ardour@9.7:path:line` references. Installed-resource references may corroborate a
  factory binding, but are not the source of truth for capability claims.

## Mapping Rules

- Every assessed record has exactly one `Preferred` mapping.
- Keep current behavior as `Current fallback` when it differs from the preferred implementation.
- `Similar` mappings must state the concrete semantic difference in `note`.
- Keyboard and keyboard-hold mappings require an Ardour XML `keyToken`; list alternate keys in
  `note` until the contract supports multiple tokens.
- `Profile Lua` mappings must identify the public Lua API or native actions involved and address
  selection, state, and undo behavior.
- Do not infer a missing capability only from a missing default binding.
- Key occupancy: Live Preferred bindings displace leftover Ardour factory or convenience chords
  that are not themselves Preferred for a Live source. Do not preserve factory defaults for their
  own sake. When two Live Preferred mappings compete for the same Ardour context and key token,
  choose by Live context priority or rehome the lower-priority Live action; keep `Key conflict`
  evidence until resolved.

## Workflow

1. Inspect the Live source action, input, and context.
2. Locate Ardour 9.7 action registration, callback behavior, and factory bindings.
3. Inspect public Lua APIs when no action is sufficient.
4. Check the proposed key against the Ardoton profile.
5. Record evidence, alternatives, and unresolved reasons.
6. Run the formatter, vocabulary generator, validator, tests, Ruff, and `git diff --check`.
