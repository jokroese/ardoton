local profile_dir = assert (arg[1], "profile directory is required")

-- Load the JSON helper relative to this script's own location so the check works
-- regardless of the caller's current working directory. ardour9-lua does not set
-- arg[0] (only arg[1+]), so derive the path from debug.getinfo instead.
local source = debug.getinfo (1, "S").source
local script_dir = "./"
if source:sub (1, 1) == "@" then
	script_dir = source:sub (2):match ("(.*/)") or "./"
end
local json = dofile (script_dir .. "json.lua")

local manifest_path = profile_dir .. "/scripts/manifest.json"
local manifest_file = assert (io.open (manifest_path, "r"))
local manifest = json.decode (manifest_file:read ("*a"))
manifest_file:close ()

-- Syntax-check every script the manifest knows about: everything bound to a slot, plus
-- anything listed as unslotted (session-init templates etc. that aren't LuaAction scripts).
local seen = {}
local script_files = {}
for _, entry in ipairs (manifest.unslotted or {}) do
	if not seen[entry] then
		seen[entry] = true
		table.insert (script_files, entry)
	end
end
for _, entry in ipairs (manifest.slots) do
	if not seen[entry.source] then
		seen[entry.source] = true
		table.insert (script_files, entry.source)
	end
end

for _, filename in ipairs (script_files) do
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

-- Bytecode/slot-assignment check: every manifest slot must be present in the installed
-- action-script state and must load as a valid Ardour-compiled factory.
local action_state_path = profile_dir .. "/ui-scripts/ardourton-actions.lua-state"
local action_state = assert (io.open (action_state_path, "rb"))
local serialized_actions = action_state:read ("*a")
action_state:close ()

local action_environment = setmetatable ({ scripts = {} }, { __index = _G })
assert (load (serialized_actions, "@" .. action_state_path, "t", action_environment)) ()

for _, entry in ipairs (manifest.slots) do
	local slot = entry.slot
	local action = assert (action_environment.scripts[slot], "missing action slot " .. slot)
	local factory = assert (load (action.f, "ardourton-action-" .. slot, "b"))
	assert (type (factory) == "function", "invalid action factory " .. slot)
	assert (type (factory ()) == "function", "invalid action body " .. slot)
end

print ("Lua checks passed")
