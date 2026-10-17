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

# Graphs: qnapd only reads its own status file here, so this never touches
# the hardware or wakes sleeping disks.
configure_collectd_conf_qnap_plugin:
  file.managed:
    - name: "/etc/collectd/collectd.conf.d/qnap.conf"
    - contents: |
        LoadPlugin exec
        <Plugin exec>
            Exec "nobody" "/usr/sbin/qnapd" "collectd"
        </Plugin>
