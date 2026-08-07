ardour {
	["type"] = "EditorAction",
	name = "Ardourton: Clear Region Fades",
	author = "Ardourton",
	license = "GPL-2.0-or-later",
	description = [[Deactivate the fade-in and fade-out of the selected audio region(s) and
reset both fade lengths to Ardour's 64-sample minimum, so the previous fade shape does not
come back if fades are re-enabled. Ardour clamps set_fade_in_length/set_fade_out_length to
64 samples, so a zero-length fade is not representable. Native Region/toggle-region-fades
only toggles fade active state and keeps the old length; this is closer to Live's "delete
fades/crossfades". MIDI-only selections are skipped.]]
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
