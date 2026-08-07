-- Minimal JSON decoder for reading profile/scripts/manifest.json under Ardour's bundled
-- Lua runtime (ardour9-lua), which ships no JSON module. Handles exactly the JSON subset our
-- manifest uses: objects, arrays, strings (with the standard backslash escapes), numbers,
-- true/false/null. Not a general-purpose parser -- do not reuse for arbitrary JSON.

local M = {}

local function skip_ws (s, i)
	local _, j = s:find ("^[ \t\r\n]*", i)
	return j + 1
end

local decode_value

local function decode_string (s, i)
	assert (s:sub (i, i) == "\"", "expected string at " .. i)
	local out = {}
	local j = i + 1
	while true do
		local c = s:sub (j, j)
		assert (c ~= "", "unterminated string")
		if c == "\"" then
			return table.concat (out), j + 1
		elseif c == "\\" then
			local e = s:sub (j + 1, j + 1)
			local map = { ["\""] = "\"", ["\\"] = "\\", ["/"] = "/", b = "\b", f = "\f", n = "\n", r = "\r", t = "\t" }
			if map[e] then
				table.insert (out, map[e])
				j = j + 2
			elseif e == "u" then
				local hex = s:sub (j + 2, j + 5)
				table.insert (out, utf8 and utf8.char (tonumber (hex, 16)) or ("\\u" .. hex))
				j = j + 6
			else
				error ("bad escape at " .. j)
			end
		else
			table.insert (out, c)
			j = j + 1
		end
	end
end

local function decode_number (s, i)
	local m, j = s:match ("^(%-?%d+%.?%d*[eE]?[%+%-]?%d*)()", i)
	assert (m, "expected number at " .. i)
	return tonumber (m), j
end

local function decode_array (s, i)
	local out = {}
	i = skip_ws (s, i + 1)
	if s:sub (i, i) == "]" then
		return out, i + 1
	end
	while true do
		local v
		v, i = decode_value (s, i)
		table.insert (out, v)
		i = skip_ws (s, i)
		local c = s:sub (i, i)
		if c == "," then
			i = skip_ws (s, i + 1)
		elseif c == "]" then
			return out, i + 1
		else
			error ("expected ',' or ']' at " .. i)
		end
	end
end

local function decode_object (s, i)
	local out = {}
	i = skip_ws (s, i + 1)
	if s:sub (i, i) == "}" then
		return out, i + 1
	end
	while true do
		local key
		key, i = decode_string (s, i)
		i = skip_ws (s, i)
		assert (s:sub (i, i) == ":", "expected ':' at " .. i)
		i = skip_ws (s, i + 1)
		local v
		v, i = decode_value (s, i)
		out[key] = v
		i = skip_ws (s, i)
		local c = s:sub (i, i)
		if c == "," then
			i = skip_ws (s, i + 1)
		elseif c == "}" then
			return out, i + 1
		else
			error ("expected ',' or '}' at " .. i)
		end
	end
end

decode_value = function (s, i)
	i = skip_ws (s, i)
	local c = s:sub (i, i)
	if c == "\"" then
		return decode_string (s, i)
	elseif c == "{" then
		return decode_object (s, i)
	elseif c == "[" then
		return decode_array (s, i)
	elseif c == "t" and s:sub (i, i + 3) == "true" then
		return true, i + 4
	elseif c == "f" and s:sub (i, i + 4) == "false" then
		return false, i + 5
	elseif c == "n" and s:sub (i, i + 3) == "null" then
		return nil, i + 4
	else
		return decode_number (s, i)
	end
end

function M.decode (s)
	local v = decode_value (s, 1)
	return v
end

return M
