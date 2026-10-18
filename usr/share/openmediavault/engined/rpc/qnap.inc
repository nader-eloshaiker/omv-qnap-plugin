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
		$this->registerMethod("getFanSettings");
		$this->registerMethod("setFanSettings");
		$this->registerMethod("getHardwareSettings");
		$this->registerMethod("setFrontPanelSettings");
		$this->registerMethod("setPowerSettings");
		$this->registerMethod("setDriverSettings");
		$this->registerMethod("setButtonSettings");
		$this->registerMethod("getTasks");
		$this->registerMethod("setupDrivers");
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

	/**
	 * Fan control page: the settings with fan speeds as percent.
	 */
	public function getFanSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$db = \OMV\Config\Database::getInstance();
		$result = $db->getAssoc("conf.service.qnap");
		foreach (["manual", "min", "max"] as $key) {
			$result["{$key}speed"] = (int)round($result["{$key}pwm"] * 100 / 255);
		}
		return $result;
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
		if ($params['minspeed'] > $params['maxspeed']) {
			throw new \OMV\Exception(gettext(
				"The minimum fan speed must not be greater than the maximum fan speed."));
		}
		// The page shows percent; the config (and qnapd) use PWM 0-255.
		foreach (["manual", "min", "max"] as $key) {
			$params["{$key}pwm"] = (int)round($params["{$key}speed"] * 255 / 100);
			unset($params["{$key}speed"]);
		}
		return $this->setSubset($params);
	}

	public function getHardwareSettings($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		$db = \OMV\Config\Database::getInstance();
		$result = $db->getAssoc("conf.service.qnap");
		$info = $this->qnapd(["info", "--json"]);
		$packages = $info['driver_packages'] ?? [];
		$installed = array_filter(array_column($packages, 'installed'));
		$outdated = array_filter($packages, function($p) {
			return !empty($p['installed']) && $p['installed'] !== $p['bundled'];
		});
		$missing = count($packages) > count($installed);
		if (!empty($info['hwmon']) && $missing) {
			$result['driverstatus'] = gettext(
				"Running, but not installed properly: click Set up drivers.");
		} else if (!empty($info['hwmon'])) {
			$result['driverstatus'] = empty($outdated) ?
				gettext("Ready ✓") :
				gettext("Ready. A driver update is available: click Set up drivers.");
		} else if (!empty($installed)) {
			$result['driverstatus'] = gettext(
				"Installed but not running: click Set up drivers, or restart the NAS.");
		} else {
			$result['driverstatus'] = gettext(
				"Not set up yet: click Set up drivers below.");
		}
		$result['leds'] = implode(", ", $info['leds'] ?? []);
		$result['rebootefiactive'] = !empty($info['reboot_efi']) ?
			gettext("Yes") : gettext("No");
		$result['headersstatus'] = !empty($info['headers']) ?
			gettext("Ready ✓") :
			gettext("Missing: click Set up drivers.");
		$cards = array_map(function($card) {
			return sprintf("%s (%s, PIC %s)", $card['model'] ?? "",
				$card['name'] ?? "", $card['pic_version'] ?? "?");
		}, $info['qm2'] ?? []);
		$result['qm2cards'] = !empty($cards) ? implode(", ", $cards) :
			gettext("None found");
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
	 * One-click driver setup (Drivers page): install the kernel headers and
	 * the driver packages shipped with the plugin, (re)load the drivers,
	 * load them at boot and turn fan control on.
	 */
	public function setupDrivers($params, $context)
	{
		$this->validateMethodContext($context, ["role" => OMV_ROLE_ADMINISTRATOR]);
		\OMV\System\Apt::assertNotLocked();
		$info = $this->qnapd(["info", "--json"]);
		$headers = $info['header_packages'] ?? [];
		$debs = array_column($info['driver_packages'] ?? [], 'path');
		foreach ($headers as $package) {
			if (!preg_match('/^[a-z0-9][a-z0-9.+-]+$/', $package)) {
				throw new \OMV\Exception(sprintf(gettext(
					"Unexpected package name '%s'."), $package));
			}
		}
		foreach ($debs as $path) {
			if (!preg_match('#^/usr/share/openmediavault-qnap/drivers/[a-z0-9-]+_[A-Za-z0-9.+~-]+_all\.deb$#', $path)) {
				throw new \OMV\Exception(sprintf(gettext(
					"Unexpected driver package '%s'."), $path));
			}
		}
		if (empty($debs)) {
			throw new \OMV\Exception(gettext(
				"The driver packages are missing. Reinstall the openmediavault-qnap plugin."));
		}
		return $this->execBgProc(function($bgStatusFilename, $bgOutputFilename)
				use ($headers, $debs, $context) {
			$say = function($text) use ($bgOutputFilename) {
				file_put_contents($bgOutputFilename, "\n" . $text . "\n",
					FILE_APPEND);
			};
			$run = function(array $args) {
				$cmd = new \OMV\System\Process($args);
				$cmd->setQuiet(TRUE);
				try {
					$cmd->execute($output, $exitStatus);
				} catch (\Exception $e) {
					return FALSE;
				}
				return 0 === $exitStatus;
			};
			$apt = function(array $packages) use ($bgOutputFilename) {
				$cmd = new \OMV\System\Process("apt-get", array_merge(
					["--yes", "--no-install-recommends", "install"], $packages));
				$cmd->setRedirect2to1();
				$cmd->setEnv("DEBIAN_FRONTEND", "noninteractive");
				return [$cmd, $this->exec($cmd, $output, $bgOutputFilename),
					$output];
			};
			$say(gettext("Step 1 of 4: installing the files needed to build the drivers (kernel headers) ..."));
			if (!empty($headers) && 0 !== $apt($headers)[1]) {
				$say(gettext("The kernel headers could not be installed; continuing, but the drivers may not build."));
			}
			$say(gettext("Step 2 of 4: installing and building the drivers. This can take a few minutes ..."));
			list($cmd, $exitStatus, $output) = $apt($debs);
			if (0 !== $exitStatus) {
				throw new \OMV\ExecException($cmd, $output, $exitStatus);
			}
			$say(gettext("Step 3 of 4: starting the drivers (the fans run at full speed for a moment) ..."));
			$run(["systemctl", "stop", "qnapd"]);
			$run(["modprobe", "-r", "qm2mod"]);
			$run(["modprobe", "-r", "qnap8528"]);
			$skip = FALSE;
			if (!$run(["modprobe", "qnap8528"])) {
				// Models with an ENE embedded controller fail the chip check.
				$skip = $run(["modprobe", "qnap8528", "skip_hw_check=true"]);
			}
			$run(["modprobe", "qm2mod"]);
			$info = $this->qnapd(["info", "--json"]);
			if (empty($info['hwmon'])) {
				throw new \OMV\Exception(gettext(
					"The drivers are installed, but the hardware driver did not start on this model. Restart the NAS and open this page again. If it still says it is not running, please report your model on GitHub."));
			}
			$say(gettext("Step 4 of 4: loading the drivers at every start and turning on fan control ..."));
			$db = \OMV\Config\Database::getInstance();
			$object = $db->get("conf.service.qnap");
			$object->set("loadmodule", TRUE);
			$object->set("loadqm2", !empty($info['qm2']));
			if ($skip) {
				$object->set("skiphwcheck", TRUE);
			}
			$object->set("enable", TRUE);
			$db->set($object);
			\OMV\Rpc\Rpc::call("Config", "applyChanges",
				["modules" => [], "force" => FALSE], $context);
			$say(gettext("Done. Your QNAP's fans, lights and buttons are now managed by OpenMediaVault. You can close this window."));
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
		return $this->friendlyRows($status['rows'] ?? [],
			$status['slots'] ?? []);
	}

	/**
	 * Plain, short names for the Status page and dashboard grid (whose
	 * tiles show about 10 characters): "Processor" instead of
	 * "Package id 0", "Bay 1" instead of "sda", and so on.
	 */
	private function friendlyRows(array $rows, array $slots)
	{
		$kinds = ["fan" => gettext("Fan"), "pwm" => gettext("Fan power"),
			"temperature" => gettext("Temperature"),
			"storage" => gettext("Storage")];
		$bySlotDevice = [];
		foreach ($slots as $slot) {
			if (!empty($slot['device'])) {
				$bySlotDevice[$slot['device']] = $slot;
			}
		}
		$system = count(array_filter($rows, function($r) {
			return ($r['source'] ?? "") === "system";
		}));
		$n = 0;
		foreach ($rows as &$row) {
			$row['kind'] = $kinds[$row['type']] ?? $row['type'];
			$name = $row['name'] ?? "";
			switch ($row['source'] ?? "") {
			case "cpu":
				$row['label'] = gettext("Processor");
				break;
			case "system":
				$n++;
				$row['label'] = $system > 1 ? sprintf(gettext("Case %d"), $n) :
					gettext("Case");
				break;
			case "disk":
				$row['label'] = isset($bySlotDevice[$name]) ?
					$bySlotDevice[$name]['label'] : sprintf(gettext("Drive %s"), $name);
				break;
			case "nvme":
				$row['label'] = sprintf(gettext("SSD %d"),
					(int)substr($name, 4) + 1);
				break;
			case "qm2":
				if ($row['type'] === "temperature") {
					$row['label'] = preg_replace('/^qm2\.\d+-slot/', 'QM2 slot ',
						$name);
				} else {
					$row['label'] = $row['type'] === "fan" ?
						gettext("QM2 fan") : gettext("QM2 power");
				}
				break;
			case "fan":
				if ($row['type'] === "fan") {
					$row['label'] = sprintf(gettext("Fan %s"),
						preg_replace('/\D/', "", $name));
				} else if ($name === "pwm") {
					$row['label'] = gettext("Fan power");
				} else {
					$row['label'] = gettext("QM2 power");
				}
				break;
			case "storage":
				if ($row['value'] === "ok") {
					$row['value'] = gettext("All good");
				}
				break;
			}
		}
		return $rows;
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
				"fw_version" => gettext("Controller firmware"),
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
		$states = ["off" => gettext("Off (empty)"), "on" => gettext("Green"),
			"active" => gettext("Green, busy"), "error" => gettext("Red (fault)"),
			"locate" => gettext("Blinking red (locating)")];
		$slots = $status['slots'] ?? [];
		foreach ($slots as &$slot) {
			$slot['statetext'] = $states[$slot['state']] ?? $slot['state'];
			$slot['label'] = preg_replace('/^qm2\.(\d+) slot/', 'QM2 slot',
				$slot['label']);
		}
		return $slots;
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
