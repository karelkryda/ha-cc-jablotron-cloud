"""Support for Jablotron alarm control panels."""

from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from jablotronpy import JablotronSectionsState

from . import JablotronConfigEntry, JablotronData, JablotronDataCoordinator
from .const import COMP_ID, DOMAIN, Actions, STATE_AS_ALARM_STATE

_LOGGER = logging.getLogger(__name__)


def state_to_alarm_state(state: JablotronSectionsState | None) -> AlarmControlPanelState:
    """Convert state to AlarmControlPanelState."""

    return STATE_AS_ALARM_STATE.get(state["state"], STATE_UNKNOWN)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Register alarm panel entity for each Jablotron service section."""

    _LOGGER.debug("Adding Jablotron alarm control panel entities")
    runtime_data: JablotronData = entry.runtime_data
    # TODO: coordinator and services like this??
    coordinator = runtime_data.coordinator
    services = runtime_data.client.services

    # Get sections for each service
    entities: list[JablotronAlarmControlPanel] = []
    for service_id, service_data in services.items():
        # Get service details
        service_name = service_data["name"]
        service_type = service_data["type"]

        # Add all controllable section entities
        _LOGGER.debug("Getting available sections for service '%s'", service_name)
        alarm = service_data["alarm"]
        for section in alarm["sections"]:
            # Get section details
            section_name = section["name"]
            section_id = section["cloud-component-id"]
            partial_arm_enabled = section["partial-arm-enabled"]
            requires_authorization = section["need-authorization"]
            current_state = state_to_alarm_state(
                next(
                    filter(lambda state: state["cloud-component-id"] == section_id, alarm["states"]),
                    None
                )
            )

            # Check whether section is controllable
            if not section["can-control"]:
                _LOGGER.debug("Section '%s' is not controllable, ignoring!", section_name)

                continue

            # Add controllable section entity
            _LOGGER.debug("Adding controllable section '%s'", section_name)
            entities.append(
                JablotronAlarmControlPanel(
                    coordinator,
                    service_id,
                    service_name,
                    service_type,
                    section_id,
                    section_name,
                    partial_arm_enabled,
                    requires_authorization,
                    current_state
                )
            )

    async_add_entities(entities)


async def async_unload_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:
    """Unload alarm panel entities."""

    return True


# TODO: cleanup + what about coordinator??
class JablotronAlarmControlPanel(CoordinatorEntity[JablotronDataCoordinator], AlarmControlPanelEntity):
    """Representation of Jablotron Cloud alarm panel entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self: JablotronAlarmControlPanel,
        coordinator: JablotronDataCoordinator,
        service_id: int,
        service_name: str,
        service_type: str,
        section_id: str,
        section_name: str,
        partial_arm_enabled: bool,
        requires_authorization: bool,
        current_state: AlarmControlPanelState
    ) -> None:
        """Initialize Jablotron alarm panel."""

        # Define panel attributes
        self._attr_name = section_name
        self._attr_unique_id = f"{service_id} {section_id}"
        self._coordinator = coordinator
        self._service_id = service_id
        self._service_name = service_name
        self._service_type = service_type
        self._section_id = section_id
        self._supports_partial_arm = partial_arm_enabled
        self._authorization_required = requires_authorization
        self._attr_alarm_state = current_state

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
        action_successful = bridge.control_section(
            service_id=self._service_id,
            service_type=self._service_type,
            component_id=self._section_id,
            state=Actions.DISARM,
            pin_code=code
        )

        # Update the state and schedule an update on successful control action
        if action_successful:
            self._attr_alarm_state = AlarmControlPanelState.DISARMING
            self.async_write_ha_state()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm request."""

        # Send request to the bridge
        code = self.code_or_default_code(code)
        client = self._coordinator.client
        bridge = client.get_bridge()
        action_successful = bridge.control_section(
            service_id=self._service_id,
            service_type=self._service_type,
            component_id=self._section_id,
            state=Actions.ARM,
            pin_code=code,
            force=client.force_arm
        )

        # Update the state and schedule an update on successful control action
        if action_successful:
            self._attr_alarm_state = AlarmControlPanelState.ARMING
            self.async_write_ha_state()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send partial arm request."""

        if not self._supports_partial_arm:
            _LOGGER.error("This action is not supported for this section!")
            return

        # Send request to the bridge
        code = self.code_or_default_code(code)
        client = self._coordinator.client
        bridge = client.get_bridge()
        action_successful = bridge.control_section(
            service_id=self._service_id,
            service_type=self._service_type,
            component_id=self._section_id,
            state=Actions.PARTIAL_ARM,
            pin_code=code,
            force=client.force_arm
        )

        # Update the state and schedule an update on successful control action
        if action_successful:
            self._attr_alarm_state = AlarmControlPanelState.ARMING
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""

        _LOGGER.warning("[%s]: UPDATE ALARM", self._attr_name)

        if not self._coordinator.data or self._service_id not in self._coordinator.data:
            _LOGGER.error("No data available for service '%d'!", self._service_id)

            return

        # Get the section state from the coordinator data
        # _LOGGER.warning("[%s]: GET STATE ALARM", self._attr_name)
        sections_data = self._coordinator.data[self._service_id].get("sections", {})
        states = sections_data.get("states", [])
        if not states:
            _LOGGER.warning(
                "States data are not available for service '%d'!", self._service_id
            )

            return

        # Update the state and schedule an update
        # _LOGGER.warning("[%s]: UPDATE STATE ALARM", self._attr_name)
        _LOGGER.debug("Updating section state for service '%d'", self._service_id)
        state = next(filter(lambda data: data[COMP_ID] == self._section_id, states))
        # _LOGGER.warning("[%s]: UPDATE STATE MATCH ALARM", self._attr_name)
        match state["state"]:
            case Actions.ARM:
                # _LOGGER.warning("[%s]: ARM state", self._attr_name)
                self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
            case Actions.PARTIAL_ARM:
                # _LOGGER.warning("[%s]: PARTIAL ARM state", self._attr_name)
                self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
            case Actions.DISARM:
                # _LOGGER.warning("[%s]: DISARM state", self._attr_name)
                self._attr_alarm_state = AlarmControlPanelState.DISARMED
            case _:
                _LOGGER.error("[%s]: Unknown state", self._attr_name)
                self._attr_alarm_state = STATE_UNKNOWN

        _LOGGER.warning("[%s]: DONE UPDATE ALARM", self._attr_name)
        self.async_write_ha_state()
