ardour {
	["type"] = "EditorAction",
	name = "Ardoton: Add Return",
	author = "Ardoton",
	license = "GPL-2.0-or-later",
	description = [[Create a stereo return bus and add post-fader sends from selected tracks.]]
}

function factory ()
	local function route_exists (name)
		for route in Session:get_routes ():iter () do
			if route:name () == name then
				return true
			end
		end
		return false
	end

	local function next_return_name ()
		if not route_exists ("A Reverb") then
			return "A Reverb"
		end
		if not route_exists ("B Delay") then
			return "B Delay"
		end

		local number = 1
		while route_exists ("Return " .. number) do
			number = number + 1
		end
		return "Return " .. number
	end

	return function ()
		local selected = ARDOUR.RouteListPtr ()
		for route in Editor:get_selection ().tracks:routelist ():iter () do
			if not route:to_track ():isnil () then
				selected:push_back (route)
			end
		end

		local buses = Session:new_audio_route (
			2,
			2,
			ARDOUR.RouteGroup (),
			1,
			next_return_name (),
			ARDOUR.PresentationInfo.Flag.AudioBus,
			ARDOUR.PresentationInfo.max_order
		)

		if buses:size () == 0 then
			return
		end

		local bus = buses:front ()
		bus:presentation_info_ptr ():set_color (0xE76F51FF)

		if selected:size () > 0 then
			Session:add_internal_sends (bus, ARDOUR.Placement.PostFader, selected)
		end
	end
end
