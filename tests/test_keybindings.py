from __future__ import annotations

from support import (
    ACTION_STATE_PATH,
    format_binding_failure,
    keymap_duplicates,
    load_expectations,
    load_keymap,
)


def test_no_duplicate_keys_within_context() -> None:
    assert keymap_duplicates() == []


def test_expected_bindings_present(coverage_tracker: dict) -> None:
    bindings, _ = load_expectations()
    actual = load_keymap()
    failures: list[str] = []

    for binding in bindings:
        got = actual.get((binding.context, binding.key))
        if got != binding.action:
            # Look for same key elsewhere to improve the message.
            alt = next(
                (
                    (ctx, key, action)
                    for (ctx, key), action in actual.items()
                    if key == binding.key and action == binding.action
                ),
                None,
            )
            if got is None and alt is not None:
                failures.append(
                    format_binding_failure(
                        binding.source_id,
                        binding.context,
                        binding.key,
                        binding.action,
                        alt[0],
                        alt[1],
                        alt[2],
                    )
                )
            else:
                failures.append(
                    format_binding_failure(
                        binding.source_id,
                        binding.context,
                        binding.key,
                        binding.action,
                        binding.context if got is not None else None,
                        binding.key if got is not None else None,
                        got,
                    )
                )
            coverage_tracker[binding.source_id]["static"] = "failed"
        else:
            coverage_tracker[binding.source_id]["static"] = "passed"

    assert not failures, "\n\n".join(failures)


def test_exclusive_bindings_only_in_approved_contexts() -> None:
    _, exclusives = load_expectations()
    actual = load_keymap()
    for exclusive in exclusives:
        matches = [ctx for (ctx, key) in actual if key == exclusive.key]
        assert matches == list(exclusive.contexts), (exclusive.key, matches)


def test_action_slot_references_resolve() -> None:
    bindings, _ = load_expectations()
    state = ACTION_STATE_PATH.read_text(encoding="utf-8")
    for binding in bindings:
        if not binding.action.startswith("LuaAction/script-"):
            continue
        slot = binding.action.rsplit("-", 1)[-1]
        assert f"scripts[{slot}]" in state, binding.action
