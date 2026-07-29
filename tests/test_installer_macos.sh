#!/bin/zsh

set -euo pipefail

repo_dir="${0:A:h:h}"
test_root="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/ardourton-test.XXXXXX")"
config_dir="${test_root}/Ardour9"
original_dir="${test_root}/original"

cleanup () {
  /bin/rm -rf "${test_root}"
}
trap cleanup EXIT

/bin/mkdir -p "${config_dir}"

{
  print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
  print -r -- '<Ardour>'
  print -r -- '  <UI>'
  print -r -- '    <Option name="flat-buttons" value="0"/>'
  print -r -- '    <Option name="show-secondary-clock" value="1"/>'
  print -r -- '    <Option name="sentinel" value="preserve-me"/>'
  print -r -- '  </UI>'
  print -r -- '  <Canvas/>'
  print -r -- '</Ardour>'
} > "${config_dir}/ui_config"

local_state="scripts = {}"
encoded="$(print -rn -- "${local_state}" | /usr/bin/base64 | /usr/bin/tr -d '\n')"
{
  print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
  print -r -- '<UIScripts>'
  print -r -- "  <ActionScript lua=\"Lua 5.3\">${encoded}</ActionScript>"
  print -r -- '  <ActionHooks/>'
  print -r -- '</UIScripts>'
} > "${config_dir}/ui_scripts"

print -r -- "original keymap" > "${config_dir}/ardour.keys"
/bin/cp -R "${config_dir}" "${original_dir}"

ARDOURTON_CONFIG_DIR="${config_dir}" \
ARDOURTON_SKIP_PROCESS_CHECK=1 \
ARDOURTON_SKIP_VERSION_CHECK=1 \
  "${repo_dir}/installer/macos.sh" install

[[ -f "${config_dir}/themes/ardourton-ardour.colors" ]]
[[ -f "${config_dir}/scripts/ardourton_beat_production.lua" ]]
[[ -f "${config_dir}/ardourton/receipt" ]]
/usr/bin/xmllint --noout "${config_dir}/ui_config" "${config_dir}/ui_scripts"
/usr/bin/grep -q 'name="sentinel" value="preserve-me"' "${config_dir}/ui_config"
/usr/bin/grep -q 'name="color-file" value="ardourton"' "${config_dir}/ui_config"
/usr/bin/grep -q 'BindingSet name="Ardourton macOS"' "${config_dir}/ardour.keys"
[[ ! -e "${config_dir}/ardour-9.7.bindings" ]]

installed_payload="$(/usr/bin/sed -n 's#.*<ActionScript[^>]*>\([^<]*\)</ActionScript>.*#\1#p' "${config_dir}/ui_scripts")"
decoded="$(print -rn -- "${installed_payload}" | /usr/bin/base64 -D)"
[[ "${decoded}" == *"Ardourton: Add Stereo Audio Track"* ]]

ARDOURTON_CONFIG_DIR="${config_dir}" \
ARDOURTON_SKIP_PROCESS_CHECK=1 \
  "${repo_dir}/installer/macos.sh" restore

/usr/bin/cmp "${original_dir}/ui_config" "${config_dir}/ui_config"
/usr/bin/cmp "${original_dir}/ui_scripts" "${config_dir}/ui_scripts"
/usr/bin/cmp "${original_dir}/ardour.keys" "${config_dir}/ardour.keys"
[[ ! -e "${config_dir}/themes/ardourton-ardour.colors" ]]
[[ ! -e "${config_dir}/scripts/ardourton_beat_production.lua" ]]
[[ ! -e "${config_dir}/ardourton/receipt" ]]

print -- "macOS installer checks passed"
