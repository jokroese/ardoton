#!/bin/zsh

set -euo pipefail

command_name="${1:-status}"
installer_dir="${0:A:h}"
repo_dir="${installer_dir:h}"
profile_dir="${repo_dir}/profile"
config_dir="${ARDOURTON_CONFIG_DIR:-${HOME}/Library/Preferences/Ardour9}"
state_dir="${config_dir}/ardourton"
receipt_file="${state_dir}/receipt"
backup_root="${state_dir}/backups"

script_names=(
  ardourton_add_audio_track.lua
  ardourton_add_midi_track.lua
  ardourton_add_return.lua
  ardourton_set_loop.lua
  ardourton_duplicate_tracks.lua
  ardourton_beat_production.lua
)

targets=(
  ardour.keys
  ui_config
  ui_scripts
  instant.xml
  themes/ardourton-ardour.colors
)

for script_name in "${script_names[@]}"; do
  targets+=("scripts/${script_name}")
done

fail () {
  print -u2 -- "Ardourton: $*"
  exit 1
}

check_ardour_closed () {
  if [[ "${ARDOURTON_SKIP_PROCESS_CHECK:-0}" == "1" ]]; then
    return
  fi
  if /usr/bin/pgrep -x Ardour9 >/dev/null 2>&1; then
    fail "Quit Ardour before continuing."
  fi
}

check_version () {
  if [[ "${ARDOURTON_SKIP_VERSION_CHECK:-0}" == "1" ]]; then
    return
  fi

  local executable=""
  for candidate in \
    "/Applications/Ardour9.app/Contents/MacOS/Ardour9" \
    "${HOME}/Applications/Ardour9.app/Contents/MacOS/Ardour9"
  do
    if [[ -x "${candidate}" ]]; then
      executable="${candidate}"
      break
    fi
  done

  [[ -n "${executable}" ]] || fail "Ardour 9 was not found."

  local version_output
  version_output="$("${executable}" --version 2>&1 || true)"
  [[ "${version_output}" == *"Ardour9.7."* ]] ||
    fail "This profile supports Ardour 9.7. Detected: ${version_output##*$'\n'}"
}

backup_targets () {
  local backup_id backup_dir manifest target source destination
  backup_id="$(/bin/date -u +%Y%m%dT%H%M%SZ)-$$"
  backup_dir="${backup_root}/${backup_id}"
  manifest="${backup_dir}/manifest.tsv"

  /bin/mkdir -p "${backup_dir}/files"
  : > "${manifest}"

  for target in "${targets[@]}"; do
    source="${config_dir}/${target}"
    destination="${backup_dir}/files/${target}"
    if [[ -e "${source}" ]]; then
      /bin/mkdir -p "${destination:h}"
      /bin/cp -p "${source}" "${destination}"
      print -r -- "existing"$'\t'"${target}" >> "${manifest}"
    else
      print -r -- "absent"$'\t'"${target}" >> "${manifest}"
    fi
  done

  print -r -- "${backup_dir}"
}

merge_ui_option () {
  local file="$1"
  local option_name="$2"
  local option_value="$3"
  local temporary
  temporary="$(/usr/bin/mktemp "${TMPDIR:-/tmp}/ardourton-ui.XXXXXX")"

  /usr/bin/awk -v name="${option_name}" -v value="${option_value}" '
    BEGIN { found = 0; ui = 0 }
    {
      if (index($0, "<UI") > 0) {
        ui = 1
      }
      if (ui && index($0, "<Option name=\"" name "\"") > 0) {
        sub(/value="[^"]*"/, "value=\"" value "\"")
        found = 1
      }
      if (ui && index($0, "</UI>") > 0 && !found) {
        print "    <Option name=\"" name "\" value=\"" value "\"/>"
        found = 1
      }
      print
    }
    END {
      if (!found) {
        exit 2
      }
    }
  ' "${file}" > "${temporary}" || {
    /bin/rm -f "${temporary}"
    fail "Could not merge '${option_name}' into ui_config."
  }

  /bin/mv "${temporary}" "${file}"
}

install_ui_options () {
  local ui_config="${config_dir}/ui_config"
  if [[ ! -f "${ui_config}" ]]; then
    {
      print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
      print -r -- '<Ardour>'
      print -r -- '  <UI>'
      print -r -- '  </UI>'
      print -r -- '  <Canvas/>'
      print -r -- '</Ardour>'
    } > "${ui_config}"
  fi

  local option_name option_value
  while IFS=$'\t' read -r option_name option_value; do
    [[ -n "${option_name}" ]] || continue
    merge_ui_option "${ui_config}" "${option_name}" "${option_value}"
  done < "${profile_dir}/preferences/ui-options.tsv"
}

merge_instant_attr () {
  local file="$1"
  local element="$2"
  local attr_name="$3"
  local attr_value="$4"
  local temporary
  temporary="$(/usr/bin/mktemp "${TMPDIR:-/tmp}/ardourton-instant.XXXXXX")"

  /usr/bin/awk -v element="${element}" -v attr="${attr_name}" -v value="${attr_value}" '
    BEGIN {
      open_tag = "<" element " "
    }
    {
      if (index($0, open_tag) > 0) {
        # Require a boundary before the attribute name so we never rewrite
        # pre-internal-grid-type / internal-grid-type when merging grid-type.
        pattern = "(^|[ \\t])" attr "=\"[^\"]*\""
        if (match($0, pattern)) {
          matched = substr($0, RSTART, RLENGTH)
          prefix = matched
          sub(attr "=\"[^\"]*\"$", attr "=\"" value "\"", prefix)
          $0 = substr($0, 1, RSTART - 1) prefix substr($0, RSTART + RLENGTH)
        } else {
          sub(/\/?>/, " " attr "=\"" value "\"&")
        }
      }
      print
    }
  ' "${file}" > "${temporary}" || {
    /bin/rm -f "${temporary}"
    fail "Could not merge '${attr_name}' into ${element} in instant.xml."
  }

  /bin/mv "${temporary}" "${file}"
}

install_instant_xml () {
  local instant_xml="${config_dir}/instant.xml"
  if [[ ! -f "${instant_xml}" ]]; then
    {
      print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
      print -r -- '<instant>'
      print -r -- '  <Editor grid-type="GridTypeBeatDiv32" snap-mode="SnapMagnetic"/>'
      print -r -- '</instant>'
    } > "${instant_xml}"
    return
  fi

  local element
  for element in Editor MIDICueEditor; do
    if /usr/bin/grep -q "<${element} " "${instant_xml}"; then
      merge_instant_attr "${instant_xml}" "${element}" "grid-type" "GridTypeBeatDiv32"
      merge_instant_attr "${instant_xml}" "${element}" "snap-mode" "SnapMagnetic"
    fi
  done
}

install_ui_scripts () {
  local ui_scripts="${config_dir}/ui_scripts"
  local fragment="${profile_dir}/ui-scripts/ardourton-actions.lua-state"
  local decoded encoded temporary
  decoded="$(/usr/bin/mktemp "${TMPDIR:-/tmp}/ardourton-actions.XXXXXX")"
  temporary="$(/usr/bin/mktemp "${TMPDIR:-/tmp}/ardourton-scripts.XXXXXX")"

  if [[ -f "${ui_scripts}" ]]; then
    encoded="$(/usr/bin/sed -n 's#.*<ActionScript[^>]*>\([^<]*\)</ActionScript>.*#\1#p' "${ui_scripts}")"
    [[ -n "${encoded}" ]] || fail "Could not read Ardour's ui_scripts file."
    print -rn -- "${encoded}" | /usr/bin/base64 -D > "${decoded}"
  else
    print -r -- "scripts = {}" > "${decoded}"
  fi

  if ! /usr/bin/grep -q 'Ardourton: Add Stereo Audio Track' "${decoded}"; then
    print >> "${decoded}"
    /bin/cat "${fragment}" >> "${decoded}"
  fi

  encoded="$(/usr/bin/base64 < "${decoded}" | /usr/bin/tr -d '\n')"

  if [[ -f "${ui_scripts}" ]]; then
    /usr/bin/awk -v payload="${encoded}" '
      {
        if (index($0, "<ActionScript") > 0) {
          sub(/>[^<]*<\/ActionScript>/, ">" payload "</ActionScript>")
        }
        print
      }
    ' "${ui_scripts}" > "${temporary}"
    /bin/mv "${temporary}" "${ui_scripts}"
  else
    {
      print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
      print -r -- '<UIScripts>'
      print -r -- "  <ActionScript lua=\"Lua 5.3\">${encoded}</ActionScript>"
      print -r -- '  <ActionHooks/>'
      print -r -- '</UIScripts>'
    } > "${ui_scripts}"
  fi

  /bin/rm -f "${decoded}" "${temporary}"
}

install_profile () {
  check_ardour_closed
  check_version
  [[ ! -f "${receipt_file}" ]] || fail "Ardourton is already installed. Restore it first."

  /bin/mkdir -p "${config_dir}" "${state_dir}" "${backup_root}"

  local backup_dir
  backup_dir="$(backup_targets)"

  /bin/mkdir -p "${config_dir}/themes" "${config_dir}/scripts"
  /bin/cp -p \
    "${profile_dir}/keybindings/macos/ardour.keys" \
    "${config_dir}/ardour.keys"
  /bin/cp -p \
    "${profile_dir}/theme/ardourton-ardour.colors" \
    "${config_dir}/themes/ardourton-ardour.colors"

  local script_name
  for script_name in "${script_names[@]}"; do
    /bin/cp -p \
      "${profile_dir}/scripts/${script_name}" \
      "${config_dir}/scripts/${script_name}"
  done

  install_ui_options
  install_instant_xml
  install_ui_scripts

  {
    print -r -- "version=0.2.3"
    print -r -- "backup=${backup_dir}"
  } > "${receipt_file}"

  print -- "Ardourton installed."
  print -- "Backup: ${backup_dir}"
  print -- "Restart Ardour to load the profile."
}

restore_profile () {
  check_ardour_closed
  [[ -f "${receipt_file}" ]] || fail "No Ardourton installation receipt was found."

  local backup_dir
  backup_dir="$(/usr/bin/sed -n 's/^backup=//p' "${receipt_file}")"
  [[ -n "${backup_dir}" && -f "${backup_dir}/manifest.tsv" ]] ||
    fail "The recorded backup is missing."

  local state target destination source
  while IFS=$'\t' read -r state target; do
    destination="${config_dir}/${target}"
    /bin/rm -f "${destination}"
    if [[ "${state}" == "existing" ]]; then
      source="${backup_dir}/files/${target}"
      /bin/mkdir -p "${destination:h}"
      /bin/cp -p "${source}" "${destination}"
    fi
  done < "${backup_dir}/manifest.tsv"

  /bin/rm -f "${receipt_file}"
  /usr/bin/rmdir "${config_dir}/themes" "${config_dir}/scripts" 2>/dev/null || true

  print -- "Ardourton restored the pre-install configuration."
  print -- "Backup retained at: ${backup_dir}"
}

show_status () {
  if [[ -f "${receipt_file}" ]]; then
    print -- "Ardourton is installed in ${config_dir}."
  else
    print -- "Ardourton is not installed in ${config_dir}."
  fi
}

case "${command_name}" in
  install) install_profile ;;
  restore) restore_profile ;;
  status) show_status ;;
  *) fail "Usage: $0 {install|restore|status}" ;;
esac
