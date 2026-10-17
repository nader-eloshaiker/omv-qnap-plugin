# -*- coding: utf-8 -*-
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
"""Graphs for the values `qnapd collectd` feeds to collectd (exec-qnap)."""
import glob
import os
import re

import openmediavault.mkrrdgraph

COLORS = ['#ff1300', '#0bb6ff', '#00df00', '#fdaf00', '#9b59b6', '#1abc9c',
          '#e67e22', '#4cd964']

TEMPERATURE_LABELS = {
    'cpu': 'CPU',
    'system': 'System (EC)',
    'disk': 'Hard disks',
    'nvme': 'NVMe',
    'qm2': 'QM2 slots',
}

# (graph, collectd type, title, vertical label, GPRINT unit)
GRAPHS = [
    ('temperature', 'temperature', 'Temperatures (hottest per source)',
     'Celsius', 'C'),
    ('fanspeed', 'fanspeed', 'Fan speed', 'RPM', 'RPM'),
    ('duty', 'percent', 'Fan duty', 'Percent', '%%'),
]


def label(kind, name):
    """Human label for a type instance written by `qnapd collectd`."""
    if kind == 'temperature':
        return TEMPERATURE_LABELS.get(name, name)
    # Chassis: fan1, fan2 ... and pwm. QM2 cards: qm2_<n>_fan1, qm2_<n>_pwm.
    match = re.match(r'qm2_(\d+)_', name)
    if match:
        index = int(match.group(1))
        return 'QM2' if index == 0 else 'QM2 #{}'.format(index + 1)
    if name == 'pwm':
        return 'Chassis'
    return 'Chassis {}'.format(name)


class Plugin(openmediavault.mkrrdgraph.IPlugin):
    def create_graph(self, config):
        for graph, kind, title, vlabel, unit in GRAPHS:
            config['instance'] = 'exec-qnap-{}'.format(graph)
            image_filename = '{image_dir}/{instance}-{period}.png'.format(
                **config)
            rrd_files = sorted(glob.glob('{}/exec-qnap/{}-*.rrd'.format(
                config['data_dir'], kind)))
            if not rrd_files:
                openmediavault.mkrrdgraph.copy_placeholder_image(
                    image_filename)
                continue

            args = []
            # yapf: disable
            # pylint: disable=line-too-long
            # autopep8: off
            args.append(image_filename)
            args.extend(config['defaults'])
            args.extend(['--start', config['start']])
            args.extend(['--title', '"QNAP {}{}"'.format(title, config['title_by_period'])])
            args.append('--slope-mode')
            args.extend(['--lower-limit', '0'])
            args.extend(['--vertical-label', vlabel])
            for index, rrd_file in enumerate(rrd_files):
                name = os.path.basename(rrd_file)[len(kind) + 1:-len('.rrd')]
                color = COLORS[index % len(COLORS)]
                args.append('DEF:v{}={}:value:AVERAGE'.format(index, rrd_file))
                args.append('DEF:x{}={}:value:MAX'.format(index, rrd_file))
                args.append('LINE1:v{}{}:"{:<12}"'.format(index, color, label(kind, name)))
                args.append('GPRINT:x{}:MAX:"%5.0lf {} Max"'.format(index, unit))
                args.append('GPRINT:v{}:LAST:"%5.0lf {} Last\\l"'.format(index, unit))
            args.append('COMMENT:"{last_update}"'.format(**config))
            # autopep8: on
            # yapf: enable
            openmediavault.mkrrdgraph.call_rrdtool_graph(args)
        return 0
