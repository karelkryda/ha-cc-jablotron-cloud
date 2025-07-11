"""Utils for Jablotron Cloud integration."""

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import STATE_UNKNOWN
from jablotronpy import JablotronSectionsState, JablotronProgrammableGatesState

from .const import STATE_AS_ALARM_STATE, STATE_AS_BINARY_STATE


def get_section_state(section_id: str, states: list[JablotronProgrammableGatesState]) -> str | None:
    """Return Jablotron section state."""

    # Get section state dict
    section_state = next(filter(lambda state: state["cloud-component-id"] == section_id, states), None)
    if not section_state:
        return None

    # Return section state value
    section_state: JablotronSectionsState
    return section_state["state"]


def section_state_to_alarm_state(state: str | None) -> AlarmControlPanelState:
    """Convert section state to AlarmControlPanelState."""

    return STATE_AS_ALARM_STATE.get(state, STATE_UNKNOWN)


def get_pg_state(gate_id: str, states: list[JablotronProgrammableGatesState]) -> str | None:
    """Return Jablotron programmable gate state."""

    # Get gate state dict
    gate_state = next(filter(lambda state: state["cloud-component-id"] == gate_id, states), None)
    if not gate_state:
        return None

    # Return gate state value
    gate_state: JablotronProgrammableGatesState
    return gate_state["state"]


def pg_state_to_binary_state(state: str | None) -> bool:
    """Convert programmable gate state to boolean value."""

    return STATE_AS_BINARY_STATE.get(state, False)
