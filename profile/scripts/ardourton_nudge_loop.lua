ardour {
	["type"] = "EditorAction",
	name = "Ardourton: Nudge Loop",
	author = "Ardourton",
	license = "GPL-2.0-or-later",
	description = [[Nudge the session loop range earlier or later by the current nudge-clock distance, keeping loop length fixed.

Not undo-safe: Ardour's Lua bindings expose no way to register a Location edit on the undo
stack (Location has no to_stateful()/to_statefuldestructible() cast, and MementoCommand<Location>
is C++-only), so Cmd+Z will not revert this edit. Ardour has no per-clip loop brace, so this
always acts on the single session auto-loop range.]]
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

		-- get_nudge_distance (pos, next) is a LuaBridge ref-out binding; the primary
		-- Lua return value is the real timecnt_t distance (see EditingContext::get_nudge_distance,
		-- gtk2_ardour/editing_context.h). Verify this against Ardour's own Lua console
		-- (Window -> Scripting -> Lua Console) before relying on it -- this binding's exact
		-- calling convention was inferred from analogous ref-out scripts (see
		-- share/scripts/s_pluginutils.lua's use of get_parameter_descriptor), not observed
		-- directly for this method.
		local dist = Editor:get_nudge_distance (loop:start (), Temporal.timecnt_t (0))

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
