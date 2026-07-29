ardour {
	["type"] = "EditorAction",
	name = "Ardourton: Add MIDI Track",
	author = "Ardourton",
	license = "GPL-2.0-or-later",
	description = [[Add a stereo-output MIDI track without assuming an instrument plugin.]]
}

function route_setup ()
	return {
		["how_many"] = 1,
		["name"] = "MIDI",
		["strict_io"] = true,
		["insert_at"] = ARDOUR.PresentationInfo.max_order,
		["group"] = false,
		["instrument"] = true,
	}
end

function factory (params)
	return function ()
		local p = params or {}
		local instrument = p["instrument"]
		if type (instrument) ~= "userdata" then
			instrument = ARDOUR.PluginInfo ()
		end

		local tracks = Session:new_midi_track (
			ARDOUR.ChanCount (ARDOUR.DataType ("midi"), 1),
			ARDOUR.ChanCount (ARDOUR.DataType ("audio"), 2),
			p["strict_io"] ~= false,
			instrument,
			nil,
			p["group"] or ARDOUR.RouteGroup (),
			p["how_many"] or 1,
			p["name"] or "MIDI",
			p["insert_at"] or ARDOUR.PresentationInfo.max_order,
			ARDOUR.TrackMode.Normal,
			true
		)

		for track in tracks:iter () do
			track:presentation_info_ptr ():set_color (0x9B73E6FF)
		end
	end
end
