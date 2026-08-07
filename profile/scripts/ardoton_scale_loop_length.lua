ardour {
	["type"] = "EditorAction",
	name = "Ardoton: Scale Loop Length",
	author = "Ardoton",
	license = "GPL-2.0-or-later",
	description = [[Halve or double the session loop range's length, keeping its start fixed.

Not undo-safe: Ardour's Lua bindings expose no way to register a Location edit on the undo
stack, so Cmd+Z will not revert this edit. Acts on the single session auto-loop range; Ardour
has no per-clip loop brace. Not grid-quantized: this scales the exact current length, matching
Location:set_end's own semantics rather than snapping to the grid.]]
}

function route_setup ()
	return {
		["numerator"] = 2,
		["denominator"] = 1,
	}
end

function factory (params)
	return function ()
		local loop = Session:locations ():auto_loop_location ()
		if not loop then
			return
		end

		local p = params or {}
		local numerator = p["numerator"] or 2
		local denominator = p["denominator"] or 1

		local scaled = loop:length ():scale (Temporal.ratio (numerator, denominator))
		local new_end = loop:start () + scaled

		-- set_end (pos, force) returns -1 and refuses the change if it would violate
		-- Config->get_range_location_minimum() -- halving a very short loop can
		-- legitimately no-op. Lua scripts have no default UI feedback on failure, so
		-- surface it in the log rather than failing silently.
		local result = loop:set_end (new_end, false)
		if result ~= 0 then
			print ("Ardoton: loop is already at its minimum length, cannot shorten further")
		end
	end
end
