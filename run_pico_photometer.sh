#!/bin/bash
# -*- coding: utf-8 -*-

# Copyright 2023 Julian Schwanbeck (schwan@umn.edu)
# ##Explanation
# This file starts the photometer.
# This file is part of pico_photometer. pico_photometer is free software: you can distribute it and/or modify
# it under the terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version. pico_photometer is distributed in
# the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public License along with pico_photometer. If
# not, see <https://www.gnu.org/licenses/>.

# See:
# https://askubuntu.com/questions/519/how-do-i-write-a-shell-script-to-install-a-list-of-applications/956410#956410
set -eu -o pipefail

if ! command -v mpremote &> /dev/null
then
    echo "mpremote could not be found"
    exit
fi

echo "Starting mpremote, disconnecting & connecting (auto: first available pico) to reset pico,
mounting local folder and running ./pico_photometer.py"

# further arguments: setrtc - sets the clock, currently buggy (20230524)
# See: https://github.com/orgs/micropython/discussions/9096#discussioncomment-5785470

exec mpremote disconnect connect reset setrtc auto mount . run "$(dirname "$0")/pico_photometer.py"
