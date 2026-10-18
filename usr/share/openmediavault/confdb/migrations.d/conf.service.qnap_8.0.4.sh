#!/usr/bin/env dash
#
# This file is part of openmediavault-qnap.
#
# openmediavault-qnap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# openmediavault-qnap is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with openmediavault-qnap. If not, see <http://www.gnu.org/licenses/>.

set -e

. /usr/share/openmediavault/scripts/helper-functions

# Buttons and buzzer (8.0.4).
xpath="/config/services/qnap"
if ! omv_config_exists "${xpath}/beep"; then
	omv_config_add_key "${xpath}" "beep" "0"
fi
if ! omv_config_exists "${xpath}/usbcopytask"; then
	omv_config_add_key "${xpath}" "usbcopytask" ""
fi
if ! omv_config_exists "${xpath}/resettask"; then
	omv_config_add_key "${xpath}" "resettask" ""
fi

exit 0
