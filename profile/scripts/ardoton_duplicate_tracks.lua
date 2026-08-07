ardour {
	["type"] = "EditorAction",
	name = "Ardoton: Duplicate Tracks",
	author = "Ardoton",
	license = "GPL-2.0-or-later",
	description = [[Open Ardour's duplicate-tracks operation for the selected tracks or busses.]]
}

function factory ()
	return function ()
		Editor:access_action ("Main", "duplicate-routes")
	end
end
