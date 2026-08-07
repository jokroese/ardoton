ardour {
	["type"] = "EditorAction",
	name = "Ardourton: Clear Region Fades",
	author = "Ardourton",
	license = "GPL-2.0-or-later",
	description = [[Deactivate and zero the fade-in and fade-out of the selected audio
region(s). Native Region/toggle-region-fades only toggles fade active state; this also zeroes
fade length, which is closer to Live's "delete fades/crossfades" behavior. MIDI-only
selections are skipped.]]
}

function factory ()
	return function ()
		local sel = Editor:get_selection ()

		Session:begin_reversible_command ("Clear Fades")

		for r in sel.regions:regionlist ():iter () do
			local ar = r:to_audioregion ()
			if not ar:isnil () then
				r:to_stateful ():clear_changes ()

				ar:set_fade_in_active (false)
				ar:set_fade_out_active (false)
				ar:set_fade_in_length (0)
				ar:set_fade_out_length (0)

				Session:add_stateful_diff_command (r:to_statefuldestructible ())
			end
		end

		if not Session:abort_empty_reversible_command () then
			Session:commit_reversible_command (nil)
		end
	end
end
