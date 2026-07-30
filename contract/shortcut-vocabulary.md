# Shortcut Contract Vocabulary

Generated from `contract/shortcut-schema.json`; do not edit manually.

Regenerate with `uv run python tools/generate_shortcut_vocabulary.py --write`.

## Source input kind

The physical input Live documents for the source shortcut.

- `Keyboard`: A discrete keyboard shortcut.
- `Keyboard hold`: A keyboard shortcut whose hold duration matters.
- `Mouse gesture`: A mouse-only gesture.
- `Modifier gesture`: A modifier combined with a pointer gesture.
- `Accessibility command`: An accessibility-oriented command.

## Audit status

Completeness of the audit, independent of implementation or verification.

- `Needs audit`: No mapping candidates have been recorded.
- `Partially assessed`: Candidates or a current fallback exist, but no preferred mapping is selected.
- `Assessed`: Exactly one preferred mapping has been selected.

## Mapping role

Relationship of a mapping candidate to the intended behavior.

- `Preferred`: The recommended implementation after audit.
- `Current fallback`: Behavior currently installed but not the preferred solution.
- `Alternative`: A viable but non-preferred candidate.

## Implementation type

Technical mechanism required to provide the mapping.

- `Profile keybinding`: An existing native Ardour action only needs a profile binding.
- `Profile Lua`: Public Ardour Lua APIs or actions can compose the behavior.
- `None`: Existing Ardour behavior already matches without profile work.
- `Ardour action patch`: Existing behavior needs a bindable Ardour action.
- `Ardour input patch`: Input routing, key state, or focus dispatch must change.
- `Ardour UI patch`: A view, control, or UI focus behavior must change.
- `Ardour engine patch`: An underlying model or engine capability is absent.

## Mapping class

Semantic fidelity between the Live source behavior and the Ardour mapping.

- `Exact`: The documented behavior matches materially.
- `Similar`: A related behavior exists with a documented semantic difference.
- `No equivalent`: No matching Ardour capability exists.

## Capability availability

Availability of the underlying capability, not whether a key is bound or installed.

- `Native`: A native Ardour capability exists.
- `Lua accessible`: The capability is available through public Lua APIs.
- `UI only`: Related UI behavior exists but lacks the required action or focus behavior.
- `Missing`: The required capability is absent after a documented capability audit.
- `Unknown`: Availability has not yet been established.

## Mapping status

Implementation lifecycle state, independent of audit completion.

- `Proposed`: Audited but not implemented.
- `Implemented`: Installed in the profile or delivered in Ardour.
- `Blocked`: Cannot proceed without resolving a concrete blocker.
- `Rejected`: Candidate considered and not selected for implementation.

## Evidence kind

Authoritative artifact used to support an evidence claim.

- `Action registration`: Registered Ardour action definition.
- `Callback implementation`: Implementation behind an existing action or UI behavior.
- `Lua API`: Public Lua API exposed by Ardour.
- `Default binding`: Factory Ardour key binding.
- `Profile binding`: Ardourton profile key binding.
- `Ardour manual`: Official Ardour user documentation.
- `Manual test`: Observed behavior in the installed Ardour build.
- `E2E test`: Automated behavior verification.
- `Capability audit`: Documented source search for a missing or UI-only capability.
- `Key conflict`: Occupied proposed key in an overlapping context.

## Evidence claim

Narrow fact supported by one evidence artifact.

- `Target exists`: An existing registered action target was located.
- `Building block exists`: Related native behavior exists, but the proposed target itself is new.
- `Behavior candidate`: Source inspection supports a behavioral conclusion not yet exercised.
- `Binding exists`: A factory or profile key binding exists.
- `Lua feasible`: Public Lua APIs expose the required primitive.
- `UI only`: Related UI behavior exists but no required bindable behavior was found.
- `Capability missing`: A documented capability audit found no required model or behavior.
- `Key conflict`: A proposed key is already occupied in an overlapping context.
- `Behavior verified`: Manual or automated execution verified the behavior.

## Evidence result

Confidence assigned to the individual evidence claim.

- `Confirmed`: The narrow claim is directly established.
- `Candidate`: The claim is source-based and not behaviorally exercised.
- `Conflict`: The key is occupied by a different action.
