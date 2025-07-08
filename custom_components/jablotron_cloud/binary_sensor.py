"""Support for Jablotron PG sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronDataCoordinator
from .const import COMP_ID, DOMAIN, SERVICE_TYPE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up programmable gate binary sensor for Jablotron Cloud from config entry."""

    coordinator: JablotronDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    services: dict[int, dict] = coordinator.data

    if not services:
        return

    # Prepare entities to be created
    entities: list[JablotronProgrammableGate] = []
    for service_id, service_data in services.items():
        gates_data: dict = service_data["gates"]
        if not gates_data:
            continue

        gates = gates_data.get("programmableGates", [])
        for gate in gates:
            gate_controllable: bool = gate["can-control"]

            if not gate_controllable:
                friendly_name: str = gate["name"]
                gate_id: str = gate[COMP_ID]

                # Add uncontrollable gate entity
                _LOGGER.debug("Adding uncontrollable gate '%s'", friendly_name)
                entities.append(
                    JablotronProgrammableGate(
                        coordinator, friendly_name, service_id, gate_id
                    )
                )

    async_add_entities(entities, True)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""

    return True


class JablotronProgrammableGate(
    CoordinatorEntity[JablotronDataCoordinator], BinarySensorEntity
):
    """Representation of Jablotron programmable gate."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self: JablotronProgrammableGate,
        coordinator: JablotronDataCoordinator,
        friendly_name: str,
        service_id: int,
        gate_id: str
    ) -> None:
        """Initialize Jablotron programmable gate binary sensor."""

        # Define sensor attributes
        self._attr_name = friendly_name
        self._attr_unique_id = f"{service_id} {gate_id}"
        self._coordinator = coordinator
        self._service_id = service_id
        self._service_name: str = coordinator.data[service_id]["service"]["name"]
        self._service_type: str = coordinator.data[service_id]["service"][SERVICE_TYPE]
        self._gate_id = gate_id

        # Initialize binary sensor
        super().__init__(coordinator)

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""

        if not self._coordinator.data or self._service_id not in self._coordinator.data:
            _LOGGER.error("No data available for service '%d'!", self._service_id)

            return

        # Get gates from the coordinator data
        _LOGGER.debug("Updating gate state for service '%d'", self._service_id)
        gates_data = self._coordinator.data[self._service_id].get("gates", {})
        states = gates_data.get("states", [])
        state = next(filter(lambda data: data[COMP_ID] == self._gate_id, states))

        # Update the state and schedule an update
        self._attr_is_on = not state["state"] == "OFF"
        self.async_write_ha_state()
