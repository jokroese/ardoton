-- Run under Ardour's own bundled Lua build only:
--   ardour9-lua tools/dump_lua_action.lua <script.lua> <slot> <display-name> [params-lua-literal]
--
-- Loads the given script the same way tests/check_lua.lua does (sandboxed environment,
-- capture the `factory` global), then dumps its compiled bytecode with string.dump() and
-- prints one `scripts[N] = { ... }` action-script fragment line to stdout.
--
-- string.dump() output is only valid for Ardour's own bytecode loader (see
-- tests/test_lua_runtime.py::test_incompatible_action_state_fails, which exists specifically
-- to prove system-Lua bytecode is rejected) -- this must run via ardour9-lua, not any other
-- Lua interpreter, or the resulting profile/ui-scripts/ardourton-actions.lua-state fragment
-- will fail to load in real Ardour.

local script_path = assert (arg[1], "usage: dump_lua_action.lua <script.lua> <slot> <name> [params]")
local slot = assert (tonumber (arg[2]), "slot number required")
local name = assert (arg[3], "display name required")
local params_literal = arg[4] or "{}"

local descriptor
local environment = setmetatable ({
	ardour = function (value)
		descriptor = value
	end,
}, { __index = _G })

-- Same loading convention as tests/check_lua.lua's syntax check: loadfile with an explicit
-- environment (Lua 5.2+ signature, which is what ardour9-lua accepts elsewhere in this repo).
-- ardour9-lua often exits 0 even after a script error and prints "Error: ..." on stdout, so
-- failures must be detected here and written to stderr for the Python orchestrator.
-- Prefer error() over os.exit(): ardour9-lua's os table has no exit().
local chunk, load_err = loadfile (script_path, "t", environment)
if not chunk then
	error ("loadfile failed: " .. tostring (load_err))
end
local ok, run_err = pcall (chunk)
if not ok then
	error ("script error: " .. tostring (run_err))
end

local source_file = assert (io.open (script_path, "r"), "cannot open " .. script_path)
local source_text = source_file:read ("*a")
source_file:close ()

assert (descriptor and descriptor.name and descriptor.type, "no ardour{} descriptor: " .. script_path)
assert (type (environment.factory) == "function", "no factory(): " .. script_path)

-- Match Ardour's own serializer (gtk2_ardour/luainstance.cc): string.dump(f, true)
-- strips debug info. At runtime Ardour does load(f)(a) — f is factory, a is params.
local bytecode = assert (string.dump (environment.factory, true), "string.dump failed for " .. script_path)

-- Ardour's action-script state is UTF-8 text with binary fields escaped as \NNN decimal
-- byte escapes (see existing profile/ui-scripts/ardourton-actions.lua-state). Lua's %q is
-- not safe here: for bytes >= 128 it emits the raw byte, which breaks UTF-8 stdout and the
-- Python orchestrator that expects a text fragment.
local function quote_lua_string (s)
	local parts = { '"' }
	for i = 1, #s do
		local b = string.byte (s, i)
		if b == 34 then -- "
			parts[#parts + 1] = '\\"'
		elseif b == 92 then -- \
			parts[#parts + 1] = '\\\\'
		elseif b == 10 then
			parts[#parts + 1] = '\\n'
		elseif b == 13 then
			parts[#parts + 1] = '\\r'
		elseif b == 9 then
			parts[#parts + 1] = '\\t'
		elseif b >= 32 and b <= 126 then
			parts[#parts + 1] = string.char (b)
		else
			parts[#parts + 1] = string.format ("\\%03d", b)
		end
	end
	parts[#parts + 1] = '"'
	return table.concat (parts)
end

io.write (string.format (
	'scripts[%d] = {} scripts[%d]["n"] = %s scripts[%d]["a"] = %s scripts[%d]["f"] = %s scripts[%d]["s"] = %s\n',
	slot, slot, quote_lua_string (name),
	slot, params_literal,
	slot, quote_lua_string (bytecode),
	slot, quote_lua_string (source_text)
))
