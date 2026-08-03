# Adaptive grid and snap

Ardourton does not implement a new snap engine. Stock Ardour 9.7 already scales most
drag/edit snaps with zoom (`SnapToGrid_Scaled`). The shipped profile only seeds defaults
so that mechanism is active and feels closer to Ableton Live.

## Why these values

| Setting | Value | Role |
|---|---|---|
| `grid-type` | `GridTypeBeatDiv32` | Ceiling for adaptive resolution (menu label “1/128 Note”). High enough that zoom + ruler granularity usually govern density instead of the menu. |
| `snap-mode` | `SnapMagnetic` | Enables snap with a screen-pixel pull radius (closest Live analog). `SnapOff` short-circuits snap entirely. |
| `ruler-granularity` | `250` | Fed into `compute_bbt_ruler_scale()`'s density threshold, not a literal spacing target — see derivation below. |
| `snap-threshold` | `10` | Magnetic pull radius in screen pixels (tighter than stock 25). |
| `snap-target` | `SnapTargetBoth` | Snap to grid and to clip/marker edges together. |
| `rulers-follow-grid` | `1` | Ruler ticks track grid-mode changes automatically. |

`GridTypeBeatDiv32` looks extreme as a fixed grid; as a **ceiling** it is intentional. With
`SnapMagnetic` and a tuned `ruler-granularity`, zoom continuously chooses a coarser or finer
BBT subdivision under that ceiling. Leaving stock `GridTypeBeat` caps adaptive snap at quarter
notes no matter how far you zoom in.

## `ruler-granularity`: why 250, not a smaller "denser" number

First attempt at this value was `14` (roughly half of stock's `25`), on the assumption that a
smaller pixel number means a denser, more Live-like grid. In testing this was **way too
granular** — the fix was going the wrong direction entirely.

The setting isn't a literal 1:1 target spacing between grid lines. The actual code
(`EditingContext::compute_bbt_ruler_scale()`, `editing_context.cc`) is:

```cpp
double ruler_line_granularity = UIConfiguration::instance().get_ruler_granularity ();  // R, your setting
ruler_line_granularity = visible_canvas_width() / (ruler_line_granularity * 5);        // note the *5

double beat_density = ((beats + 1) * (...)) / ruler_line_granularity;

if (beat_density > 16)      scale = bbt_show_quarters;   // show every beat
else if (beat_density > 2)  scale = bbt_show_eighths;
...
```

Substituting `beats ≈ W/P` (where `P` is the actual on-screen pixel spacing between beats at the
current zoom, `W` the visible width) gives `beat_density ≈ 5R/P`, so at any threshold `T` the
ruler switches resolution at physical spacing `P = 5R/T`. At `T=16` — the transition from
"every 4 beats" to "every single beat," the one most noticeable in everyday use — that gives:

| `R` | `P` at the every-beat transition |
|---|---|
| 14 (first attempt) | ≈ 4–5 px — switches to dense detail while still zoomed out; unreadable |
| 25 (Ardour stock) | ≈ 8 px |
| 250 (shipped) | ≈ 78 px |

78px sits inside the ~40–80px band that's the standard convention for minimum legible
tick/label spacing in timeline UIs, and matches how Ableton visibly manages this — Live doesn't
publish its exact algorithm, but it always keeps a comfortable, readable line spacing rather than
maximizing density, and shows the user its current grid spacing for exactly that reason (Arrangement
View, §6.10 of the [Ableton manual](https://www.ableton.com/en/manual/arrangement-view/)).

This approximation gets less reliable at the finer subdivision thresholds (`T=2,1,0.5,0.25`),
since those only trigger when few beats are visible on screen and the dropped `+1` term starts to
matter — so this derivation is strongest for, and was validated against, the coarse/fine
transition users actually notice, not a proof of exact behavior at extreme zoom-in.

## Where it is written

- `ui_config` Options come from `profile/preferences/ui-options.tsv` via the installer merge.
- `instant.xml` `<Editor>` / `<MIDICueEditor>` attributes are merged by `install_instant_xml()`
  (attribute-scoped; live state such as `playhead`, `zoom`, and `pre-internal-grid-type` are left alone).
- Canonical values are recorded under `grid_snap_defaults` in `profile/manifest.json`.

`<AudioClipEditor>` stays on its time-domain grid (`GridTypeMinSec`); the pack does not force a
musical grid there.

## Session caveat

Global `instant.xml` applies when no session is loaded and for **new** sessions. Once a session
exists, Ardour prefers that session’s own saved Editor state. Installing Ardourton does not
rewrite existing session files; open an old project and you may still see the previous
`grid-type` / `snap-mode` until you change them in-app.

## Ruler visibility is a separate fallback, not driven by grid-type

Bars:Beats / Tempo / Time Signature not showing by default is a distinct issue from the
grid-type/snap-mode seeding above — seeding a musical `grid-type` does not turn these rulers on.

`Editor::restore_ruler_visibility()` (`editor_rulers.cc:418-475`) reads a per-session
`<RulerVisibility>` node from the session's own extra XML (a different store from `instant.xml`).
When that node doesn't exist yet (any brand-new session), it falls back to
`_session->config.get_default_time_domain()`: Bars:Beats/Tempo/Time-Signature are only switched on
if the session's time domain is `BeatTime`. Ardour's session default is `AudioTime` unless
something sets it otherwise, so new sessions start with those three rulers off regardless of
`grid-type`.

The one thing that *would* auto-correct this — `Editor::show_rulers_for_grid()`, which force-shows
the musical rulers for any musical grid type — only runs from
`EditingContext::grid_type_chosen()`, which is itself gated by
`!ARDOUR_UI::instance()->loading_session()` (`editing_context.cc:945`). That guard exists so
grid-type restoration during load doesn't clobber ruler visibility the user set by hand. It also
means the seeded `grid-type` in `instant.xml` never gets a chance to trigger the ruler fix at
startup — manually reselecting the grid afterward "fixes" it only because
`loading_session()` is false by then and the click re-fires the same code path for real.

Two Lua-level candidates were checked and ruled out before landing on the actual fix:

- **`SessionLoad`/`SessionClose`** Lua signals don't exist — `#if 0`'d out in
  `gtk2_ardour/luasignal_syms.inc.h:22-24`.
- **`SetSession`** (`// emitted when a session is loaded`, `luainstance.cc:1547`) does exist, but
  fires too early to help: `ARDOUR_UI::set_session()` is called from inside
  `build_session_stage_two()` / `load_session_stage_two()`, both wrapped end-to-end in
  `PBD::Unwinder uw (_loading_session, true)`. A hook on `SetSession` would run while
  `_loading_session` is still `true` — same guard, same no-op.

**Fix, in `profile/scripts/ardourton_beat_production.lua`'s `factory()`:**

```lua
Editor:set_toggleaction ("Rulers", "toggle-bbt-ruler", true)
Editor:set_toggleaction ("Rulers", "toggle-meter-ruler", true)
Editor:set_toggleaction ("Rulers", "toggle-tempo-ruler", true)
```

`Editor:set_toggleaction()` → `ActionManager::set_toggleaction_state()` (`libs/gtkmm2ext/actions.cc:224`)
sets an *absolute* toggle state (`tact->set_active(s)`, a no-op if already correct) and has no
`loading_session()` guard — only `Editor::toggle_ruler_visibility()`'s own `no_ruler_shown_update`
flag, which `restore_ruler_visibility()` has already cleared by this point in session construction
(confirmed via the call order in `Editor::set_session()`, `editor.cc:1338-1344`: rulers are
restored, *then* `set_state()` applies grid-type). So this runs safely and takes effect
immediately, right before the template calls `Session:save_state("")`.

**Scope:** this only fixes sessions created via the "Ardourton: Beat Production" template, since
that's the only place the fix is wired in. A session started from a blank New Session or a
different template will still start with these rulers off. There is no confirmed
template-independent hook in Ardour 9.7 to fix this globally — see the `SessionLoad`/`SetSession`
findings above.

## Known gap

A few Ardour call sites hardcode `SnapToGrid_Unscaled` (fixed to the menu grid type regardless
of zoom). Fixing those needs an Ardour source patch, not a profile change.
