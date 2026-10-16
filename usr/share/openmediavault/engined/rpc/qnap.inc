<?php
/**
 * This file is part of openmediavault-qnap.
 *
 * openmediavault-qnap is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * any later version.
 *
 * openmediavault-qnap is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with openmediavault-qnap. If not, see <http://www.gnu.org/licenses/>.
 */

class OMVRpcServiceQnap extends \OMV\Rpc\ServiceAbstract
{
	public function getName()
	{
		return "Qnap";
	}

	public function initialize()
	{
		$this->registerMethod("getSettings");
		$this->registerMethod("setFanSettings");
		$this->registerMethod("getHardwareSettings");
		$this->registerMethod("setHardwareSettings");
		$this->registerMethod("getStatus");
	}

	public function getSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$db = \OMV\Config\Database::getInstance();
		return $db->getAssoc("conf.service.qnap");
	}

	public function setFanSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$this->validateMethodParams($params, "rpc.qnap.setfansettings");
		foreach (["cpu" => "cpu", "sys" => "system", "disk" => "disk",
				"nvme" => "nvme"] as $prefix => $title) {
			if ($params["{$prefix}low"] >= $params["{$prefix}high"]) {
				throw new \OMV\Exception(sprintf(gettext(
					"The %s start temperature must be lower than the full speed temperature."),
					$title));
			}
		}
		if ($params['minpwm'] > $params['maxpwm']) {
			throw new \OMV\Exception(gettext(
				"The minimum fan speed must not be greater than the maximum fan speed."));
		}
		return $this->setSubset($params);
	}

	public function getHardwareSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$db = \OMV\Config\Database::getInstance();
		$result = $db->getAssoc("conf.service.qnap");
		$info = $this->qnapd(["info", "--json"]);
		$result['driverstatus'] = !empty($info['hwmon']) ?
			gettext("Loaded") : gettext("Not loaded");
		$result['ecfirmware'] = $info['fw_version'] ?? "";
		$result['boardmodel'] = trim(sprintf("%s %s",
			$info['mainboard_model'] ?? "", $info['backplane_model'] ?? ""));
		$result['leds'] = implode(", ", $info['leds'] ?? []);
		$result['rebootefiactive'] = !empty($info['reboot_efi']) ?
			gettext("Yes") : gettext("No");
		$cards = array_map(function($card) {
			return sprintf("%s (%s, PIC %s)", $card['model'] ?? "",
				$card['name'] ?? "", $card['pic_version'] ?? "?");
		}, $info['qm2'] ?? []);
		if (!empty($cards)) {
			$result['qm2cards'] = implode(", ", $cards);
		} else {
			$result['qm2cards'] = !empty($info['qm2_loaded']) ?
				gettext("None found") : gettext("qm2mod driver not loaded");
		}
		return $result;
	}

	public function setHardwareSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$this->validateMethodParams($params, "rpc.qnap.sethardwaresettings");
		return $this->setSubset($params);
	}

	/**
	 * Current fan and temperature readings, as rows of
	 * {type, source, name, label, value, unit}.
	 */
	public function getStatus($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$status = $this->qnapd(["status", "--json"]);
		return $status['rows'] ?? [];
	}

	private function setSubset($params)
	{
		$db = \OMV\Config\Database::getInstance();
		$object = $db->get("conf.service.qnap");
		$object->setAssoc($params);
		$db->set($object);
		return $object->getAssoc();
	}

	private function qnapd(array $args)
	{
		$cmd = new \OMV\System\Process(array_merge(["/usr/sbin/qnapd"], $args));
		$cmd->setQuiet(TRUE);
		$cmd->execute($output, $exitStatus);
		if (0 !== $exitStatus) {
			return [];
		}
		$result = json_decode(implode("", $output), TRUE);
		return is_array($result) ? $result : [];
	}
}
