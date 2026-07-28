#!/bin/zsh

set -e
repo_dir="${0:A:h}"
exec "${repo_dir}/installer/macos.sh" restore
