ardour {
	["type"] = "EditorAction",
	name = "Ardoton: Add Stereo Audio Track",
	author = "Ardoton",
	license = "GPL-2.0-or-later",
	description = [[Add a stereo audio track at the end of the session.]]
}

function route_setup ()
	return {
		["how_many"] = 1,
		["name"] = "Audio",
		["channels"] = 2,
		["track_mode"] = ARDOUR.TrackMode.Normal,
		["strict_io"] = true,
		["insert_at"] = ARDOUR.PresentationInfo.max_order,
		["group"] = false,
		["instrument"] = nil,
	}
end

function factory (params)
	return function ()
		local p = params or {}
		local tracks = Session:new_audio_track (
			p["channels"] or 2,
			2,
			p["group"] or ARDOUR.RouteGroup (),
			p["how_many"] or 1,
			p["name"] or "Audio",
			p["insert_at"] or ARDOUR.PresentationInfo.max_order,
			p["track_mode"] or ARDOUR.TrackMode.Normal,
			true
		)

		for track in tracks:iter () do
			track:set_strict_io (p["strict_io"] ~= false)
			track:presentation_info_ptr ():set_color (0x4C8EDAFF)
		end
	end
end
