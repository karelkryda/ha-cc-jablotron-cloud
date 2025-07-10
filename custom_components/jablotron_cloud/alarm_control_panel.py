"""Support for Jablotron alarm control panels."""

from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity, AlarmControlPanelEntityFeature, \
    AlarmControlPanelState, CodeFormat
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from jablotronpy import JablotronSectionsState, IncorrectPinCodeException

from . import JablotronConfigEntry, JablotronData, JablotronDataCoordinator, JablotronClient
from .const import DOMAIN, STATE_AS_ALARM_STATE

_LOGGER = logging.getLogger(__name__)


def state_to_alarm_state(state: JablotronSectionsState | None) -> AlarmControlPanelState:
    """Convert state to AlarmControlPanelState."""

    return STATE_AS_ALARM_STATE.get(state["state"], STATE_UNKNOWN)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: F841
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Register alarm panel entity for each Jablotron service section."""

    _LOGGER.debug("Adding Jablotron alarm control panel entities")
    runtime_data: JablotronData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    # Get sections for each service
    entities: list[JablotronAlarmControlPanel] = []
    for service_id, service_data in client.services.items():
        # Get service details
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

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
                    client,
                    service_id,
                    service_name,
                    service_type,
                    service_firmware,
                    section_id,
                    section_name,
                    partial_arm_enabled,
                    requires_authorization,
                    current_state
                )
            )

    async_add_entities(entities)


async def async_unload_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:  # noqa: F841
    """Unload alarm panel entities."""

    return True


class JablotronAlarmControlPanel(CoordinatorEntity[JablotronDataCoordinator], AlarmControlPanelEntity):
    """Representation of Jablotron Cloud alarm panel entity."""

    # Allow custom entity names
    _attr_has_entity_name = True

    def __init__(
        self: JablotronAlarmControlPanel,
        coordinator: JablotronDataCoordinator,
        client: JablotronClient,
        service_id: int,
        service_name: str,
        service_type: str,
        service_firmware: str,
        section_id: str,
        section_name: str,
        partial_arm_enabled: bool,
        requires_authorization: bool,
        current_state: AlarmControlPanelState
    ) -> None:
        """Initialize Jablotron alarm panel."""

        # Define entity attributes
        self._client = client
        self._service_id = service_id
        self._service_name = service_name
        self._service_type = service_type
        self._service_firmware = service_firmware
        self._section_id = section_id
        self._section_name = section_name

        # Define panel attributes
        self._attr_name = section_name
        self._attr_unique_id = f"{service_id}_{section_id}"
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

        supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
        if self._supports_partial_arm:
            supported_features |= AlarmControlPanelEntityFeature.ARM_HOME

        return supported_features

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about device."""

        return DeviceInfo(
            identifiers={(DOMAIN, str(self._service_id))},
            name=self._service_name,
            manufacturer="Jablotron",
            model=self._service_type,
            sw_version=self._service_firmware
        )

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm request."""

        # Send disarm request to section
        try:
            code = self.code_or_default_code(code)
            bridge = self._client.get_bridge()
            disarm_successful = bridge.control_section(
                service_id=self._service_id,
                service_type=self._service_type,
                component_id=self._section_id,
                state="DISARM",
                pin_code=code
            )

            # Set state to disarming if disarm action was successful
            if disarm_successful:
                self._attr_alarm_state = AlarmControlPanelState.DISARMING
                self.async_write_ha_state()
        except IncorrectPinCodeException:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_pin"
            )

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm request."""

        # Send arm request to section
        try:
            code = self.code_or_default_code(code)
            bridge = self._client.get_bridge()
            arm_successful = bridge.control_section(
                service_id=self._service_id,
                service_type=self._service_type,
                component_id=self._section_id,
                state="ARM",
                pin_code=code,
                force=self._client.force_arm
            )

            # Set state to arming if arm action was successful
            if arm_successful:
                self._attr_alarm_state = AlarmControlPanelState.ARMING
                self.async_write_ha_state()
        except IncorrectPinCodeException:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_pin"
            )

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send partial arm request."""

        # Check that partial arm is supported
        if not self._supports_partial_arm:
            return

        # Send partial arm request to section
        try:
            code = self.code_or_default_code(code)
            bridge = self._client.get_bridge()
            arm_successful = bridge.control_section(
                service_id=self._service_id,
                service_type=self._service_type,
                component_id=self._section_id,
                state="PARTIAL_ARM",
                pin_code=code,
                force=self._client.force_arm
            )

            # Set state to arming if partial arm action was successful
            if arm_successful:
                self._attr_alarm_state = AlarmControlPanelState.ARMING
                self.async_write_ha_state()
        except IncorrectPinCodeException:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_pin"
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""

        # Get corresponding service data
        _LOGGER.debug("Updating alarm state for section '%s'", self._section_name)
        service = self._client.services.get(self._service_id, None)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)

            return

        # Get service states
        states = service["alarm"].get("states", None)
        if not states:
            _LOGGER.warning("No states data available for service '%d'!", self._service_id)

            return

        # Set current section state
        self._attr_alarm_state = state_to_alarm_state(
            next(
                filter(lambda state: state["cloud-component-id"] == self._section_id, states),
                None
            )
        )
        self.async_write_ha_state()

        _LOGGER.debug("Successfully updated alarm state for section '%s'", self._section_name)
