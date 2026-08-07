ardour {
	["type"] = "EditorAction",
	name = "Ardourton: Duplicate Time",
	author = "Ardourton",
	license = "GPL-2.0-or-later",
	description = [[Copy the selected time range and paste it immediately after itself, across
every track it spans -- matching Live's in-place "Duplicate Time" rather than native
copy/paste-section, which pastes at the edit point instead.]]
}

function factory ()
	return function ()
		local ok, ext = Editor:get_selection_extents (Temporal.timepos_t (0), Temporal.timepos_t (0))
		if not ok then
			return
		end

		local start_pos = ext[1]
		local end_pos = ext[2]

		-- Session::cut_copy_section wraps its own begin_reversible_command / playlist-diff /
		-- commit internally (libs/ardour/session.cc), so this call is undo-safe with no
		-- extra work here.
		Session:cut_copy_section (start_pos, end_pos, end_pos, ARDOUR.SectionOperation.CopyPaste)
	end
end
