ardour {
	["type"] = "EditorAction",
	name = "Ardourton: Resize Loop End",
	author = "Ardourton",
	license = "GPL-2.0-or-later",
	description = [[Shorten or lengthen the session loop range by nudging its end point by the
current nudge-clock distance.

Not undo-safe: Ardour's Lua bindings expose no way to register a Location edit on the undo
stack, so Cmd+Z will not revert this edit. Acts on the single session auto-loop range; Ardour
has no per-clip loop brace. Satisfies both S08-11 ("Shorten/Lengthen
Loop") and S16-12 ("Adjust Loop Brace Length") -- their audit records cross-reference each
other as the same target.]]
}

function route_setup ()
	return {
		["direction"] = 1,
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

		-- See the calling-convention caveat in ardourton_nudge_loop.lua -- same binding.
		local dist = Editor:get_nudge_distance (loop:_end (), Temporal.timecnt_t (0))

		local new_end
		if direction < 0 then
			new_end = loop:_end () - dist
		else
			new_end = loop:_end () + dist
		end

		local result = loop:set_end (new_end, false)
		if result ~= 0 then
			print ("Ardourton: loop end change rejected (would go below the minimum range length)")
		end
	end
end
