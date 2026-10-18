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
	// A locate request stops by itself after this long.
	const LOCATE_SECONDS = 600;

	public function getName()
	{
		return "Qnap";
	}

	public function initialize()
	{
		$this->registerMethod("getSettings");
		$this->registerMethod("setFanSettings");
		$this->registerMethod("getHardwareSettings");
		$this->registerMethod("setFrontPanelSettings");
		$this->registerMethod("setPowerSettings");
		$this->registerMethod("setDriverSettings");
		$this->registerMethod("setButtonSettings");
		$this->registerMethod("getTasks");
		$this->registerMethod("installHeaders");
		$this->registerMethod("getStatus");
		$this->registerMethod("getDevice");
		$this->registerMethod("getGauges");
		$this->registerMethod("getSlots");
		$this->registerMethod("locate");
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
		$result['leds'] = implode(", ", $info['leds'] ?? []);
		$result['rebootefiactive'] = !empty($info['reboot_efi']) ?
			gettext("Yes") : gettext("No");
		$result['headersstatus'] = !empty($info['headers']) ?
			sprintf(gettext("Installed for %s"), $info['kernel'] ?? "") :
			sprintf(gettext("Missing for %s: the drivers cannot be rebuilt for this kernel"),
				$info['kernel'] ?? "?");
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

	/**
	 * One setter per page (Front panel, Power, Drivers); each validates and
	 * stores only that page's fields. They share getHardwareSettings.
	 */
	public function setFrontPanelSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$this->validateMethodParams($params, "rpc.qnap.setfrontpanelsettings");
		return $this->setSubset($params);
	}

	public function setButtonSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$this->validateMethodParams($params, "rpc.qnap.setbuttonsettings");
		$uuids = array_column($this->getTasks([], $context), "uuid");
		foreach (["usbcopytask", "resettask"] as $key) {
			if (!in_array($params[$key], $uuids, TRUE)) {
				throw new \OMV\Exception(gettext(
					"The selected scheduled task no longer exists."));
			}
		}
		return $this->setSubset($params);
	}

	/**
	 * Scheduled Tasks a button can run (Buttons page), "None" first.
	 * qnapd runs the script OMV writes for the task, as the task's user.
	 */
	public function getTasks($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$db = \OMV\Config\Database::getInstance();
		$result = [["uuid" => "", "description" => gettext("None")]];
		foreach ($db->getByFilter("conf.system.cron.job", [
				"operator" => "stringEquals", "arg0" => "type",
				"arg1" => "userdefined"]) as $job) {
			$text = $job->get("comment") ?: $job->get("command");
			if (mb_strlen($text) > 60) {
				$text = mb_substr($text, 0, 57) . "...";
			}
			$result[] = [
				"uuid" => $job->get("uuid"),
				"description" => sprintf("%s (%s)", $text,
					$job->get("username"))
			];
		}
		return $result;
	}

	/**
	 * Install the kernel headers DKMS needs to build the drivers: for the
	 * running kernel and, via its metapackage, for future kernels.
	 */
	public function installHeaders($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		\OMV\System\Apt::assertNotLocked();
		$packages = $this->qnapd(["info", "--json"])['header_packages'] ?? [];
		foreach ($packages as $package) {
			if (!preg_match('/^[a-z0-9][a-z0-9.+-]+$/', $package)) {
				throw new \OMV\Exception(sprintf(gettext(
					"Unexpected package name '%s'."), $package));
			}
		}
		if (empty($packages)) {
			throw new \OMV\Exception(gettext(
				"Cannot tell which kernel headers to install."));
		}
		return $this->execBgProc(function($bgStatusFilename, $bgOutputFilename)
				use ($packages) {
			$cmd = new \OMV\System\Process("apt-get", array_merge(
				["--yes", "--no-install-recommends", "install"], $packages));
			$cmd->setRedirect2to1();
			$cmd->setEnv("DEBIAN_FRONTEND", "noninteractive");
			if (0 !== ($exitStatus = $this->exec($cmd, $output,
					$bgOutputFilename))) {
				throw new \OMV\ExecException($cmd, $output, $exitStatus);
			}
			return $output;
		});
	}

	public function setPowerSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$this->validateMethodParams($params, "rpc.qnap.setpowersettings");
		return $this->setSubset($params);
	}

	public function setDriverSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$this->validateMethodParams($params, "rpc.qnap.setdriversettings");
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

	/**
	 * Device identity as {property, value} rows (System page, dashboard).
	 */
	public function getDevice($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$info = $this->qnapd(["info", "--json"]);
		$rows = [];
		if (!empty($info['bios_version']) && !empty($info['bios_date'])) {
			$info['bios_version'] .= " ({$info['bios_date']})";
		}
		foreach ([
				"model" => gettext("Model"),
				"nickname" => gettext("Name"),
				"serial" => gettext("Serial number"),
				"bios_version" => gettext("BIOS"),
				"fw_version" => gettext("EC firmware"),
				"manufactured" => gettext("Manufactured"),
				"mainboard_model" => gettext("Mainboard"),
				"backplane_model" => gettext("Backplane"),
			] as $key => $property) {
			if (!empty($info[$key])) {
				$rows[] = ["property" => $property, "value" => $info[$key]];
			}
		}
		foreach ($info['qm2'] ?? [] as $card) {
			$rows[] = [
				"property" => gettext("QM2 card"),
				"value" => sprintf("%s (S/N %s, PIC %s)", $card['model'] ?? "",
					$card['serial'] ?? "?", $card['pic_version'] ?? "?")
			];
		}
		return $rows;
	}

	/**
	 * Flat values for the dashboard gauges: fanduty, qm2duty (%) and the
	 * hottest cpu, system, disk, nvme, qm2 temperature (null if absent).
	 */
	public function getGauges($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$status = $this->qnapd(["status", "--json"]);
		return $status['gauges'] ?? new \stdClass();
	}

	/**
	 * Drive bays and QM2 slots as qnapd reports them (Disks page).
	 */
	public function getSlots($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$status = $this->qnapd(["status", "--json"]);
		return $status['slots'] ?? [];
	}

	/**
	 * Start or stop blinking a slot's LED. Only qnapd writes LEDs: this
	 * records the request in a file it watches, and it stops by itself.
	 */
	public function locate($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$this->validateMethodParams($params, "rpc.qnap.locate");
		$ids = array_column($this->getSlots([], $context), "id");
		if (!in_array($params['id'], $ids, TRUE)) {
			throw new \OMV\Exception(sprintf(gettext("Unknown slot '%s'."),
				$params['id']));
		}
		$file = "/run/qnapd/locate.json";
		$requests = json_decode(@file_get_contents($file) ?: "{}", TRUE);
		$requests = array_filter(is_array($requests) ? $requests : [],
			function($until) { return $until > time(); });
		if ($params['enable']) {
			$requests[$params['id']] = time() + self::LOCATE_SECONDS;
		} else {
			unset($requests[$params['id']]);
		}
		if (!is_dir(dirname($file))) {
			mkdir(dirname($file), 0755, TRUE);
		}
		$tmp = $file . ".tmp";
		file_put_contents($tmp, json_encode((object)$requests));
		rename($tmp, $file);
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
		// execute() throws on a non-zero exit status; the UI should show
		// "not loaded"/empty rows rather than an error dialog.
		try {
			$cmd->execute($output, $exitStatus);
		} catch (\Exception $e) {
			return [];
		}
		if (0 !== $exitStatus) {
			return [];
		}
		$result = json_decode(implode("", $output), TRUE);
		return is_array($result) ? $result : [];
	}
}
