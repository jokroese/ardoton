ardour {
	["type"] = "EditorAction",
	name = "Ardoton: Resize Loop End",
	author = "Ardoton",
	license = "GPL-2.0-or-later",
	description = [[Shorten or lengthen the session loop range by moving its end point one bar
(the "bars" param) earlier or later, keeping the start fixed.

Deliberately a bar rather than the editor grid. Ardoton seeds grid-type to
GridTypeBeatDiv32 as an *adaptive ceiling* (docs/concepts/adaptive-grid-and-snap.md), so
Editor:get_grid_type_as_beats would report a 1/128 note here -- ~16ms at 120bpm. The
zoom-scaled resolution that makes that ceiling usable (bbt_ruler_scale, chosen in
EditingContext::compute_bbt_ruler_scale) is private and not Lua-exported, so a script cannot
see the effective on-screen grid at all. A bar is the coarsest musical unit that is both
reachable from Lua and stable against zoom.

Also deliberately not the nudge clock: that is a user-editable preference defaulting to 5
seconds (Editor::set_state, gtk2_ardour/editor.cc), which made shortening a silent no-op on
any loop of 5s or less.

Not undo-safe: Ardour's Lua bindings expose no way to register a Location edit on the undo
stack, so Cmd+Z will not revert this edit. Acts on the single session auto-loop range; Ardour
has no per-clip loop brace. Satisfies both S08-11 ("Shorten/Lengthen
Loop") and S16-12 ("Adjust Loop Brace Length") -- their audit records cross-reference each
other as the same target.]]
}

function route_setup ()
	return {
		["direction"] = 1,
		["bars"] = 1,
	}
end

function factory (params)
	return function ()
		local loop = Session:locations ():auto_loop_location ()
		if not loop then
			return
		end

		local p = params or {}
		local direction = p["direction"] or 1
		local bars = p["bars"] or 1

		local tmap = Temporal.TempoMap.read ()
		local pos = loop:_end ()

		-- Bar length in quarter-note beats, computed exactly as Ardour's own GridTypeBar
		-- step does (EditingContext::get_a_grid_type_as_beats, gtk2_ardour/editing_context.cc).
		--
		-- TempoMap:bbtwalk_to_quarters would additionally handle a meter change inside the
		-- traversed span, but Temporal.BBT_Offset's Lua constructor is bound as uint32_t
		-- (libs/ardour/luabindings.cc), so a backward walk cannot be expressed without
		-- mutating .bars after construction. Reading the meter at the loop end instead means
		-- a meter change between the old and new end is measured with the wrong bar length --
		-- the same limitation stock Ardour's own bar grid has.
		local meter = tmap:meter_at (pos)
		local bar_beats = (4.0 * meter:divisions_per_bar ()) / meter:note_value ()

		-- Resolve in the beat domain and convert back through the tempo map, so the step
		-- stays correct across a tempo change. Location:set_end coerces whatever it is given
		-- into the session's own time domain (libs/ardour/location.cc), so handing it an
		-- audio-domain position here is safe regardless of the session setting.
		local target = tmap:quarters_at (pos) + Temporal.Beats.from_double (bar_beats * bars * direction)
		local new_end = Temporal.timepos_t (tmap:sample_at_beats (target))

		-- set_end (pos, force) returns -1 without changing anything if the new end lands at
		-- or before the loop start, or closer to it than Config->get_range_location_minimum().
		-- Lua scripts have no default UI feedback on failure, so surface it in the log rather
		-- than failing silently.
		local result = loop:set_end (new_end, false)
		if result ~= 0 then
			print ("Ardoton: loop end change rejected (new end at or before the loop start, or below the minimum range length)")
		end
	end
end
