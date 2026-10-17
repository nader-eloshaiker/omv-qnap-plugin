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

# Night brightness schedule (8.0.3).
xpath="/config/services/qnap"
if ! omv_config_exists "${xpath}/lednight"; then
	omv_config_add_key "${xpath}" "lednight" "0"
fi
if ! omv_config_exists "${xpath}/lednightstart"; then
	omv_config_add_key "${xpath}" "lednightstart" "22:00"
fi
if ! omv_config_exists "${xpath}/lednightend"; then
	omv_config_add_key "${xpath}" "lednightend" "07:00"
fi
if ! omv_config_exists "${xpath}/lednightbrightness"; then
	omv_config_add_key "${xpath}" "lednightbrightness" "10"
fi

exit 0
