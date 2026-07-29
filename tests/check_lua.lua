local profile_dir = assert (arg[1], "profile directory is required")
local scripts = {
	"ardourton_add_audio_track.lua",
	"ardourton_add_midi_track.lua",
	"ardourton_add_return.lua",
	"ardourton_set_loop.lua",
	"ardourton_duplicate_tracks.lua",
	"ardourton_beat_production.lua",
}

for _, filename in ipairs (scripts) do
	local descriptor
	local environment = setmetatable ({
		ardour = function (value)
			descriptor = value
		end,
	}, { __index = _G })

	local path = profile_dir .. "/scripts/" .. filename
	local chunk = assert (loadfile (path, "t", environment))
	chunk ()
	assert (descriptor and descriptor.name and descriptor.type, filename)
	assert (type (environment.factory) == "function", filename)
end

local action_state_path = profile_dir .. "/ui-scripts/ardourton-actions.lua-state"
local action_state = assert (io.open (action_state_path, "rb"))
local serialized_actions = action_state:read ("*a")
action_state:close ()

local action_environment = setmetatable ({ scripts = {} }, { __index = _G })
assert (load (serialized_actions, "@" .. action_state_path, "t", action_environment)) ()

for slot = 28, 32 do
	local action = assert (action_environment.scripts[slot], "missing action slot " .. slot)
	local factory = assert (load (action.f, "ardourton-action-" .. slot, "b"))
	assert (type (factory) == "function", "invalid action factory " .. slot)
	assert (type (factory ()) == "function", "invalid action body " .. slot)
end

print ("Lua checks passed")
