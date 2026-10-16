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

class OMVModuleQnap extends \OMV\Engine\Module\ServiceAbstract
	implements \OMV\Engine\Notify\IListener, \OMV\Engine\Module\IServiceStatus
{
	/**
	 * Must match the salt state directory srv/salt/omv/deploy/qnap.
	 */
	public function getName()
	{
		return "qnap";
	}

	public function getDescription()
	{
		return gettext("QNAP fan, LED and front panel control.");
	}

	public function getStatus()
	{
		$db = \OMV\Config\Database::getInstance();
		$object = $db->get("conf.service.qnap");
		$systemCtl = new \OMV\System\SystemCtl("qnapd");
		return [
			"name" => $this->getName(),
			"title" => gettext("QNAP hardware"),
			"enabled" => $object->get("enable"),
			"running" => $systemCtl->isActive()
		];
	}

	public function bindListeners(\OMV\Engine\Notify\Dispatcher $dispatcher)
	{
		$dispatcher->addListener(OMV_NOTIFY_MODIFY,
			"org.openmediavault.conf.service.qnap", [$this, "setDirty"]);
	}
}
