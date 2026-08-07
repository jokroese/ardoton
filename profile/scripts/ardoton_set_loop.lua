ardour {
	["type"] = "EditorAction",
	name = "Ardoton: Set and Toggle Loop",
	author = "Ardoton",
	license = "GPL-2.0-or-later",
	description = [[Set the loop range from the current edit range, then toggle loop playback.]]
}

function factory ()
	return function ()
		Editor:access_action ("Editor", "set-loop-from-edit-range")
		Editor:access_action ("Transport", "Loop")
	end
end
