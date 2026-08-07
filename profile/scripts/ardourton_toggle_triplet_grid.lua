ardour {
	["type"] = "EditorAction",
	name = "Ardourton: Toggle Triplet Grid",
	author = "Ardourton",
	license = "GPL-2.0-or-later",
	description = [[Toggle the editor grid between its current binary subdivision and the
matching triplet subdivision.

No native binary/triplet toggle exists in Ardour (set_grid_type is not Lua-exported); this
switches via the "Snap" action group's radio actions instead. Grid types with no triplet
counterpart (Bar, Beat, Timecode, MinSec, CDFrame, None, and the 5th/7th-based divisions) are
left unchanged.]]
}

function factory ()
	-- Editing.* is only available inside a running Ardour session. Keep all references
	-- inside the returned action body so (1) ardour9-lua can load+dump this script at
	-- bytecode-build time and (2) check_lua.lua can call factory() without Editing.
	return function ()
		local binary_to_triplet = {
			[Editing.GridTypeBeatDiv2]  = "grid-type-thirds",
			[Editing.GridTypeBeatDiv4]  = "grid-type-sixths",
			[Editing.GridTypeBeatDiv8]  = "grid-type-twelfths",
			[Editing.GridTypeBeatDiv16] = "grid-type-twentyfourths",
		}

		local triplet_to_binary = {
			[Editing.GridTypeBeatDiv3]  = "grid-type-halves",
			[Editing.GridTypeBeatDiv6]  = "grid-type-quarters",
			[Editing.GridTypeBeatDiv12] = "grid-type-eighths",
			[Editing.GridTypeBeatDiv24] = "grid-type-asixteenthbeat",
		}

		local current = Editor:grid_type ()

		local to_triplet = binary_to_triplet[current]
		if to_triplet then
			Editor:access_action ("EditorSnap", to_triplet)
			return
		end

		local to_binary = triplet_to_binary[current]
		if to_binary then
			Editor:access_action ("EditorSnap", to_binary)
			return
		end
	end
end
