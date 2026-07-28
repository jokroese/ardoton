ardour {
	["type"] = "SessionInit",
	name = "Ardourton: Beat Production",
	author = "Ardourton",
	license = "GPL-2.0-or-later",
	description = [[Create a compact beat-production session with MIDI, audio, and return tracks.]],
	master_bus = 0
}

local colors = {
	amber = 0xE6A23CFF,
	teal = 0x2FB7A8FF,
	violet = 0x9B73E6FF,
	coral = 0xE76F51FF,
	blue = 0x4C8EDAFF,
	green = 0x70A86BFF,
}

local function add_audio_track (name, color, routes)
	local tracks = Session:new_audio_track (
		2,
		2,
		ARDOUR.RouteGroup (),
		1,
		name,
		ARDOUR.PresentationInfo.max_order,
		ARDOUR.TrackMode.Normal,
		true
	)
	for track in tracks:iter () do
		track:presentation_info_ptr ():set_color (color)
		routes:push_back (track)
	end
end

local function add_midi_track (name, color, routes)
	local tracks = Session:new_midi_track (
		ARDOUR.ChanCount (ARDOUR.DataType ("midi"), 1),
		ARDOUR.ChanCount (ARDOUR.DataType ("audio"), 2),
		true,
		ARDOUR.PluginInfo (),
		nil,
		ARDOUR.RouteGroup (),
		1,
		name,
		ARDOUR.PresentationInfo.max_order,
		ARDOUR.TrackMode.Normal,
		true
	)
	for track in tracks:iter () do
		track:presentation_info_ptr ():set_color (color)
		routes:push_back (track)
	end
end

local function add_return (name, color, routes)
	local buses = Session:new_audio_route (
		2,
		2,
		ARDOUR.RouteGroup (),
		1,
		name,
		ARDOUR.PresentationInfo.Flag.AudioBus,
		ARDOUR.PresentationInfo.max_order
	)
	if buses:size () == 0 then
		return
	end
	local bus = buses:front ()
	bus:presentation_info_ptr ():set_color (color)
	Session:add_internal_sends (bus, ARDOUR.Placement.PostFader, routes)
end

function factory ()
	return function ()
		if Session:master_out ():isnil () then
			Session:add_master_bus (ARDOUR.ChanCount (ARDOUR.DataType ("audio"), 2))
		end
		ARDOUR.config ():set_output_auto_connect (ARDOUR.AutoConnectOption.AutoConnectMaster)

		local routes = ARDOUR.RouteListPtr ()
		add_midi_track ("Drums", colors.amber, routes)
		add_midi_track ("Bass", colors.teal, routes)
		add_midi_track ("Chords", colors.violet, routes)
		add_midi_track ("Lead", colors.coral, routes)
		add_audio_track ("Audio", colors.blue, routes)
		add_audio_track ("Vocal", colors.green, routes)
		add_return ("A Reverb", colors.violet, routes)
		add_return ("B Delay", colors.teal, routes)

		Session:save_state ("")
	end
end
