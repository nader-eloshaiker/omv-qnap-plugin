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

{% set config = salt['omv_conf.get']('conf.service.qnap') %}
# Fault mails: OMV email on and the "qnap" event enabled (enabled when the
# event has never been saved, as the Notification page shows it).
{% set email_config = salt['omv_conf.get']('conf.system.notification.email') %}
{% set notification = salt['omv_conf.get_by_filter'](
  'conf.system.notification.notification',
  {'operator': 'stringEquals', 'arg0': 'id', 'arg1': 'qnap'}) %}
{% set _ = config.update({'notify': (email_config.enable | to_bool) and
  (notification | length == 0 or notification[0].enable | to_bool)}) %}
{% set ec_dir = '/sys/devices/platform/qnap8528/ec' %}
{% set power_recovery = {'off': 0, 'on': 1, 'last': 2} %}
{% set eup_mode = {'off': 0, 'on': 1} %}

# Kernel module loading. The drivers themselves (qnap8528-dkms, and
# qm2mod-dkms for QM2 cards) are separate packages; the plugin only
# manages how they are loaded.
{% set modules = [] %}
{% if config.loadmodule | to_bool %}{% set _ = modules.append('qnap8528') %}{% endif %}
{% if config.loadqm2 | to_bool %}{% set _ = modules.append('qm2mod') %}{% endif %}

{% if modules %}

configure_qnap_modules_load:
  file.managed:
    - name: "/etc/modules-load.d/openmediavault-qnap.conf"
    - contents: |
        {{ pillar['headers']['auto_generated'] }}
        {{ pillar['headers']['warning'] }}
        {%- for module in modules %}
        {{ module }}
        {%- endfor %}
    - user: root
    - group: root
    - mode: '0644'

{% else %}

remove_qnap_modules_load:
  file.absent:
    - name: "/etc/modules-load.d/openmediavault-qnap.conf"

{% endif %}

{% if config.loadmodule | to_bool %}

configure_qnap_modprobe:
  file.managed:
    - name: "/etc/modprobe.d/openmediavault-qnap.conf"
    - contents: |
        {{ pillar['headers']['auto_generated'] }}
        {{ pillar['headers']['warning'] }}
        options qnap8528 skip_hw_check={{ 'true' if config.skiphwcheck | to_bool else 'false' }}
    - user: root
    - group: root
    - mode: '0644'

{% else %}

remove_qnap_modprobe:
  file.absent:
    - name: "/etc/modprobe.d/openmediavault-qnap.conf"

{% endif %}

{% for module in modules %}
load_qnap_module_{{ module }}:
  cmd.run:
    - name: "modprobe {{ module }}"
    - unless: "test -d /sys/module/{{ module }}"
{%- if module == 'qnap8528' %}
    - require:
      - file: configure_qnap_modprobe
{%- endif %}
{% endfor %}

# One-shot EC settings, persisted by the EC itself.
{% if config.powerrecovery in power_recovery %}
{% set value = power_recovery[config.powerrecovery] %}
set_qnap_power_recovery:
  cmd.run:
    - name: "printf '%s' {{ value }} > {{ ec_dir }}/power_recovery"
    - onlyif: "test -w {{ ec_dir }}/power_recovery"
    - unless: "test \"$(cat {{ ec_dir }}/power_recovery)\" = \"{{ value }}\""
{% endif %}

{% if config.eupmode in eup_mode %}
{% set value = eup_mode[config.eupmode] %}
set_qnap_eup_mode:
  cmd.run:
    - name: "printf '%s' {{ value }} > {{ ec_dir }}/eup_mode"
    - onlyif: "test -w {{ ec_dir }}/eup_mode"
    - unless: "test \"$(cat {{ ec_dir }}/eup_mode)\" = \"{{ value }}\""
{% endif %}

# Kernel command line: reboot=efi fixes reboot hangs on several QNAP
# models. Uses a grub.d drop-in so /etc/default/grub is never edited.
{% if config.rebootefi | to_bool %}

configure_qnap_grub_reboot_efi:
  file.managed:
    - name: "/etc/default/grub.d/openmediavault-qnap.cfg"
    - contents: |
        {{ pillar['headers']['auto_generated'] }}
        {{ pillar['headers']['warning'] }}
        # Only once, even if reboot=efi was also added to /etc/default/grub.
        case " ${GRUB_CMDLINE_LINUX_DEFAULT} " in
        *" reboot=efi "*) ;;
        *) GRUB_CMDLINE_LINUX_DEFAULT="${GRUB_CMDLINE_LINUX_DEFAULT} reboot=efi" ;;
        esac
    - makedirs: True
    - user: root
    - group: root
    - mode: '0644'

{% else %}

configure_qnap_grub_reboot_efi:
  file.absent:
    - name: "/etc/default/grub.d/openmediavault-qnap.cfg"

{% endif %}

update_qnap_grub:
  cmd.run:
    - name: "update-grub"
    - onlyif: "command -v update-grub"
    - onchanges:
      - file: configure_qnap_grub_reboot_efi

# Daemon configuration and service.
configure_qnapd:
  file.managed:
    - name: "/etc/qnapd/qnapd.json"
    - source:
      - salt://{{ tpldir }}/files/etc-qnapd-qnapd_json.j2
    - template: jinja
    - context:
        config: {{ config | json }}
    - makedirs: True
    - user: root
    - group: root
    - mode: '0644'

{% if config.enable | to_bool %}

start_qnapd_service:
  service.running:
    - name: qnapd
    - enable: True
    - watch:
      - file: configure_qnapd

{% else %}

stop_qnapd_service:
  service.dead:
    - name: qnapd
    - enable: False

{% endif %}
