# Installer (prototype)

Not a CLI yet. Goal: a reversible pack that can **backup → apply → restore** Ardourton profile files into an Ardour 9.7 user config.

## Intended behavior

1. **Backup** — copy the user’s existing Ardour config paths that Ardourton will touch into a dated backup directory.
2. **Apply** — install files from `../profile/` (keybindings, theme, scripts, templates) into the correct Ardour locations for the current OS.
3. **Restore** — put the backup back and remove Ardourton-owned files.

## Profile layout

See `../profile/README.md` for the intended pack directories. Create each subdirectory when its first real file exists. Exact Ardour destination paths will be documented here once the first apply script exists.

## Safety

- Require Ardour to be quit before apply/restore.
- Never overwrite without a backup from this run (or an explicit `--force` later).
- Keep restore as a first-class command from day one.
