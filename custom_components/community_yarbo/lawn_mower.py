"""Lawn mower platform for Yarbo integration."""

from __future__ import annotations

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    HEAD_TYPE_LAWN_MOWER,
    HEAD_TYPE_LAWN_MOWER_PRO,
    get_activity_state,
)
from .controller import async_ensure_controller
from .coordinator import YarboDataCoordinator
from .entity import YarboEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yarbo lawn mower entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([YarboLawnMower(coordinator)])


class YarboLawnMower(YarboEntity, LawnMowerEntity):
    """Lawn mower entity — available only when mower head is installed.

    Maps Yarbo robot states to HA LawnMowerActivity:
    - working/planning active → MOWING
    - paused → PAUSED
    - returning/docked/charging → DOCKED
    - error → ERROR
    """

    _attr_translation_key = "mower"
    # Without this HA sees supported_features=0, hides the start/pause/dock
    # controls on dashboards and rejects lawn_mower.* service calls, even
    # though async_start_mowing / async_pause / async_dock are implemented.
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator: YarboDataCoordinator) -> None:
        super().__init__(coordinator, "mower")

    @property
    def available(self) -> bool:
        """Only available when lawn mower or lawn mower pro head is installed."""
        if not super().available:
            return False
        if not self.telemetry:
            return False
        return self.telemetry.head_type in (HEAD_TYPE_LAWN_MOWER, HEAD_TYPE_LAWN_MOWER_PRO)

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return current mowing activity."""
        telemetry = self.telemetry
        if not telemetry:
            return None

        # Single source of truth — see get_activity_state for why the old
        # integer comparison against telemetry.state never matched.
        activity = get_activity_state(telemetry)
        if activity == "error":
            return LawnMowerActivity.ERROR
        if activity == "working":
            return LawnMowerActivity.MOWING
        if activity == "paused":
            return LawnMowerActivity.PAUSED
        if activity == "returning":
            return LawnMowerActivity.RETURNING
        return LawnMowerActivity.DOCKED

    async def async_start_mowing(self) -> None:
        """Start mowing — resumes last plan or starts default."""
        async with self.coordinator.command_lock:
            await async_ensure_controller(self.coordinator.client)
            await self.coordinator.client.resume()

    async def async_pause(self) -> None:
        """Pause mowing."""
        async with self.coordinator.command_lock:
            await async_ensure_controller(self.coordinator.client)
            await self.coordinator.client.pause_planning()

    async def async_dock(self) -> None:
        """Return robot to dock."""
        async with self.coordinator.command_lock:
            await async_ensure_controller(self.coordinator.client)
            await self.coordinator.client.return_to_dock()
