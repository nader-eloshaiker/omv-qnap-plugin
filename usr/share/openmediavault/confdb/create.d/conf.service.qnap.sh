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

# Defaults live only in the datamodel (conf.service.qnap.json).
if ! omv-confdbadm exists "conf.service.qnap"; then
	omv-confdbadm read --defaults "conf.service.qnap" | \
		omv-confdbadm update "conf.service.qnap" -
fi

exit 0
