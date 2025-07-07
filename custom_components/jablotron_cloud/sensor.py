"""Support for Jablotron temperature sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronDataCoordinator
from .const import DEVICE_ID, DOMAIN, SERVICE_TYPE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up temperature sensor for Jablotron Cloud from config entry."""

    coordinator: JablotronDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    services: dict[int, dict] = coordinator.data

    if not services:
        return

    # Prepare entities to be created
    entities: list[JablotronSensor] = []
    for service_id, service_data in services.items():
        thermo_data: dict = service_data["thermo"]
        if not thermo_data:
            continue

        for thermo_device in thermo_data:
            device_id: str = thermo_device[DEVICE_ID]

            _LOGGER.debug("Adding thermo device '%s'", device_id)
            entities.append(
                JablotronSensor(
                    coordinator,
                    service_id,
                    device_id
                )
            )

    async_add_entities(entities, True)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""

    return True


class JablotronSensor(CoordinatorEntity[JablotronDataCoordinator], SensorEntity):
    """Representation of Jablotron temperature sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self: JablotronSensor,
        coordinator: JablotronDataCoordinator,
        service_id: int,
        device_id: str
    ) -> None:
        """Initialize Jablotron temperature sensor."""

        # Define sensor attributes
        self._attr_name = device_id
        self._attr_unique_id = f"{service_id} {device_id}"
        self._coordinator = coordinator
        self._service_id = service_id
        self._service_name: str = coordinator.data[service_id]["service"]["name"]
        self._service_type: str = coordinator.data[service_id]["service"][SERVICE_TYPE]
        self._device_id = device_id

        # Initialize sensor
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

        # Get thermo device from the coordinator data
        _LOGGER.debug("Updating thermo data for service '%d'", self._service_id)
        thermo_data = self._coordinator.data[self._service_id].get("thermo", {})
        device = next(
            filter(lambda data: data[DEVICE_ID] == self._device_id, thermo_data)
        )

        # Update the state and schedule an update
        temperature = float(device["temperature"])
        self._attr_native_value = temperature
        self.async_write_ha_state()
