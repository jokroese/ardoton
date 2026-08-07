ardour {
	["type"] = "EditorAction",
	name = "Ardoton: Move Loop by Loop Length",
	author = "Ardoton",
	license = "GPL-2.0-or-later",
	description = [[Shift the session loop range earlier or later by its own length, so the
adjacent repeat becomes the active loop.

Not undo-safe: Ardour's Lua bindings expose no way to register a Location edit on the undo
stack, so Cmd+Z will not revert this edit. Acts on the single session auto-loop range; Ardour
has no per-clip loop brace.]]
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
		local dist = loop:length ()

		local new_start
		if direction < 0 then
			new_start = loop:start () - dist
		else
			new_start = loop:start () + dist
		end

		if new_start:is_negative () then
			new_start = Temporal.timepos_t (0)
		end

		loop:move_to (new_start)
	end
end
