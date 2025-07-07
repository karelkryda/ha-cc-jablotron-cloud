"""Support for Jablotron alarm control panels."""

from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronDataCoordinator
from .const import COMP_ID, DOMAIN, SERVICE_TYPE, Actions

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up alarm panel for Jablotron Cloud from config entry."""

    coordinator: JablotronDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    services: dict[int, dict] = coordinator.data

    if not services:
        return

    # Prepare entities to be created
    entities: list[JablotronAlarmControlPanel] = []
    for service_id, service_data in services.items():
        service_name: str = service_data["service"]["name"]
        _LOGGER.debug("Discovered service '%s' as '%d'", service_name, service_id)

        sections_data: dict = service_data["sections"]
        if not sections_data:
            _LOGGER.debug("Sections data are empty, skipping service '%d'", service_id)

            continue

        sections: list[dict] = sections_data["sections"]
        if not sections:
            _LOGGER.debug("Sections are empty, skipping service '%d'", service_id)

            continue

        # Add all controllable sections as entities
        for section in sections:
            section_controllable: bool = section["can-control"]

            if section_controllable:
                friendly_name: str = section["name"]
                section_id: str = section[COMP_ID]
                partial_arm_enabled = bool(section["partial-arm-enabled"])
                requires_authorization = bool(section["need-authorization"])

                # Add controllable section entity
                _LOGGER.debug("Adding controllable section '%s'", friendly_name)
                entities.append(
                    JablotronAlarmControlPanel(
                        coordinator,
                        friendly_name,
                        service_id,
                        section_id,
                        partial_arm_enabled,
                        requires_authorization
                    )
                )

    async_add_entities(entities, True)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""

    return True


class JablotronAlarmControlPanel(
    CoordinatorEntity[JablotronDataCoordinator],
    AlarmControlPanelEntity
):
    """Representation of Jablotron Cloud alarm panel."""

    _attr_has_entity_name = True

    def __init__(
        self: JablotronAlarmControlPanel,
        coordinator: JablotronDataCoordinator,
        friendly_name: str,
        service_id: int,
        section_id: str,
        partial_arm_enabled: bool,
        requires_authorization: bool
    ) -> None:
        """Initialize Jablotron alarm panel."""

        # Define panel attributes
        self._attr_name = friendly_name
        self._attr_unique_id = f"{service_id} {section_id}"
        self._coordinator = coordinator
        self._service_id = service_id
        self._service_name: str = coordinator.data[service_id]["service"]["name"]
        self._service_type: str = coordinator.data[service_id]["service"][SERVICE_TYPE]
        self._section_id = section_id
        self._supports_partial_arm = partial_arm_enabled
        self._authorization_required = requires_authorization

        # Initialize alarm control panel
        super().__init__(coordinator)

    @property
    def code_format(self) -> CodeFormat | None:
        """Disable code for sections that don't require it."""

        return CodeFormat.NUMBER if self._authorization_required else None

    @property
    def code_arm_required(self) -> bool:
        """Whether code is required for arm actions."""

        return self._authorization_required

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return list of supported features."""

        if self._supports_partial_arm:
            return (
                AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_HOME
            )

        return AlarmControlPanelEntityFeature.ARM_AWAY

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about device."""

        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, str(self._service_id))
            },
            name=self._service_name,
            manufacturer="Jablotron",
            model=self._service_type
        )

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm request."""

        # Send request to the bridge
        code = self.code_or_default_code(code)
        bridge = self._coordinator.client.get_bridge()
        bridge.control_section(
            service_id=self._service_id,
            service_type=self._service_type,
            component_id=self._section_id,
            state=Actions.DISARM,
            pin_code=code
        )

        # Update the state and schedule an update
        self._attr_alarm_state = AlarmControlPanelState.DISARMING
        self.schedule_update_ha_state()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send forced arm request."""

        # Send request to the bridge
        code = self.code_or_default_code(code)
        bridge = self._coordinator.client.get_bridge()
        bridge.control_section(
            service_id=self._service_id,
            service_type=self._service_type,
            component_id=self._section_id,
            state=Actions.ARM,
            pin_code=code,
            force=True
        )

        # Update the state and schedule an update
        self._attr_alarm_state = AlarmControlPanelState.ARMING
        self.schedule_update_ha_state()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send forced partial arm request."""
        if not self._supports_partial_arm:
            _LOGGER.error("This action is not supported for this section!")
            return

        # Send request to the bridge
        code = self.code_or_default_code(code)
        bridge = self._coordinator.client.get_bridge()
        bridge.control_section(
            service_id=self._service_id,
            service_type=self._service_type,
            component_id=self._section_id,
            state=Actions.PARTIAL_ARM,
            pin_code=code,
            force=True
        )

        # Update the state and schedule an update
        self._attr_alarm_state = AlarmControlPanelState.ARMING
        self.schedule_update_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""

        if not self._coordinator.data or self._service_id not in self._coordinator.data:
            _LOGGER.error("No data available for service '%d'!", self._service_id)

            return

        # Get the section state from the coordinator data
        sections_data = self._coordinator.data[self._service_id].get("sections", {})
        states = sections_data.get("states", [])
        if not states:
            _LOGGER.warning(
                "States data are not available for service '%d'!", self._service_id
            )

            return

        # Update the state and schedule an update
        _LOGGER.debug("Updating section state for service '%d'", self._service_id)
        state = next(filter(lambda data: data[COMP_ID] == self._section_id, states))
        match state["state"]:
            case Actions.ARM:
                self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
            case Actions.PARTIAL_ARM:
                self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
            case Actions.DISARM:
                self._attr_alarm_state = AlarmControlPanelState.DISARMED
            case _:
                self._attr_alarm_state = STATE_UNKNOWN

        self.schedule_update_ha_state()
