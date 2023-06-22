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

# Add time stamps if possible, print normally otherwise
if ! command -v ts &> /dev/null;
then
  function ts {
    cat < /dev/stdin
  }
fi

# Set file path
if command -v realpath &> /dev/null;
then
  # If possible, expand path
  file_path=$(realpath $"$(dirname "$0")/pico_photometer.py")
else
  # Hope that this works
  file_path="./pico_photometer.py"
fi

# Test for mpremote installation
if ! command -v mpremote &> /dev/null;
then
  echo "mpremote could not be found, please install it" | ts
  echo "See: https://pypi.org/project/mpremote/" | ts
  exit 1
fi

# Test if script is present
# echo "Checking Python script under $file_path" | ts
if ! test -f "$file_path";
then
  echo "Python script not found: $file_path" | ts
  echo "Downloading file now" | ts
  wget -t -c --show-progress -O "$file_path" https://raw.githubusercontent.com/schwanbeck/pico_photometer/master/pico_photometer.py
  echo "Check correct settings in script: " "$file_path" | ts
  echo "Aborting." | ts
  exit 1
fi

# Check if device can be connected
if ! mpremote disconnect | ts;
then
  echo "Could not connect to a device, aborting." | ts
  exit 1
fi

echo "Starting mpremote, disconnecting & connecting (auto: first available pico) to reset pico,
mounting local folder and running ./pico_photometer.py" | ts
# further arguments: setrtc - sets the clock, currently buggy (20230524)
# See: https://github.com/orgs/micropython/discussions/9096#discussioncomment-5785470
# mpremote disconnect auto reset rtc --set rtc | ts
exec mpremote disconnect connect auto setrtc mount . run "$file_path" | ts
