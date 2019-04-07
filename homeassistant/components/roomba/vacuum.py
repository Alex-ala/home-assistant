"""
Support for Wi-Fi enabled iRobot Roombas.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.roomba/
"""
import asyncio
import logging

import async_timeout
import voluptuous as vol

from homeassistant.components.vacuum import (
    PLATFORM_SCHEMA, SUPPORT_BATTERY, SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME, SUPPORT_STATUS, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_LOCATE, SUPPORT_MAP, VacuumDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['roombai7==1.0']

_LOGGER = logging.getLogger(__name__)

ATTR_BIN_FULL = 'bin_full'
ATTR_BIN_PRESENT = 'bin_present'
ATTR_ERROR = 'error'
ATTR_POSITION = 'position'
ATTR_MISSION_STATE = 'mission_state'
ATTR_MISSION_NAME = 'mission_name'

CONF_FLOORPLAN = 'floorplan'
CONF_MAP = 'map'
CONF_OFFSET = 'offset'

DEFAULT_NAME = 'Roomba'

PLATFORM = 'roomba'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_FLOORPLAN): cv.string,
    vol.Optional(CONF_MAP): cv.string
}, extra=vol.ALLOW_EXTRA)

# Commonly supported features
SUPPORT_ROOMBA = SUPPORT_BATTERY | SUPPORT_PAUSE | SUPPORT_RETURN_HOME | SUPPORT_STATUS | SUPPORT_STOP | \
                 SUPPORT_TURN_OFF | SUPPORT_TURN_ON | SUPPORT_MAP | SUPPORT_LOCATE


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the iRobot Roomba vacuum cleaner platform."""
    from roombai7.controller import Controller
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    floorplan_path = config.get(CONF_FLOORPLAN)
    map_path = config.get(CONF_MAP)

    roomba = Controller(
        ip=host, blid=username, password=password)
    _LOGGER.debug("Initializing communication with host %s", host)

    try:
        with async_timeout.timeout(9):
            await hass.async_add_job(roomba.connect)
    except asyncio.TimeoutError:
        raise PlatformNotReady

    if map_path is not None:
        roomba.enable_mapping(image_drawmap_path=map_path, image_floorplan_path=floorplan_path)
    roomba_vac = RoombaVacuum(name, roomba)
    hass.data[PLATFORM][host] = roomba_vac

    async_add_entities([roomba_vac], True)


class RoombaVacuum(VacuumDevice):
    """Representation of a Roomba Vacuum cleaner robot."""

    def __init__(self, name, roomba):
        """Initialize the Roomba handler."""
        self._available = False
        self._battery_level = None
        self._is_on = False
        self._mission_name = None
        self._mission_state = None
        self._name = name
        self.vacuum = roomba

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return self._mission_state

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        bin_state = self.vacuum.get_bin_state()
        if bin_state == "Full":
            bin_full = True
            bin_present = True
        else:
            bin_full = False
            if bin_state == "Not present":
                bin_present = False
            else:
                bin_present = True
        attrs = {
            ATTR_BIN_FULL: bin_full,
            ATTR_BIN_PRESENT: bin_present,
            ATTR_MISSION_NAME: self.vacuum.get_mission_name(),
            ATTR_MISSION_STATE: self.vacuum.get_mission_state(),
            ATTR_POSITION: self.vacuum.get_position()
        }
        return attrs

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_ROOMBA

    async def async_start(self, **kwargs):
        await self.hass.async_add_job(self.vacuum.start_clean)

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        await self.hass.async_add_job(self.vacuum.start_clean)
        self._is_on = True

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        await self.async_stop()
        await self.async_return_to_base()

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self.hass.async_add_job(self.vacuum.stop)
        self._is_on = False

    async def async_resume(self, **kwargs):
        """Resume the cleaning cycle."""
        await self.hass.async_add_job(self.vacuum.resume)
        self._is_on = True

    async def async_pause(self, **kwargs):
        """Pause the cleaning cycle."""
        await self.hass.async_add_job(self.vacuum.pause)
        self._is_on = False

    async def async_quick_clean(self, **kwargs):
        """Pause the cleaning cycle."""
        await self.hass.async_add_job(self.vacuum.quick_clean)
        self._is_on = False

    async def async_spot_clean(self, **kwargs):
        """Pause the cleaning cycle."""
        await self.hass.async_add_job(self.vacuum.spot_clean)
        self._is_on = False

    async def async_training(self, **kwargs):
        """Pause the cleaning cycle."""
        await self.hass.async_add_job(self.vacuum.start_training)
        self._is_on = False

    async def async_locate(self, **kwargs):
        """Pause the cleaning cycle."""
        await self.hass.async_add_job(self.vacuum.locate_with_beep)
        self._is_on = False

    async def async_start_pause(self, **kwargs):
        """Pause the cleaning task or resume it."""
        if self.is_on:  # vacuum is running
            await self.async_pause()
        elif self._mission_state == 'stop' or self._mission_state == 'pause':  # vacuum is stopped
            await self.async_resume()
        else:  # vacuum is off
            await self.async_turn_on()

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        await self.hass.async_add_job(self.vacuum.dock)
        self._is_on = False

    async def async_set_stop_on_full_bin(self, enable, **kwargs):
        """enable/disable stop on full bin."""
        await self.hass.async_add_job(self.vacuum.set_stop_on_full_bin, enable)

    async def async_set_two_passes(self, enable, **kwargs):
        """enable/disable stop on full bin."""
        await self.hass.async_add_job(self.vacuum.set_two_passes, enable)

    async def async_update(self):
        """Fetch state from the device."""
        # No data, no update
        if not self.vacuum.is_connected():
            _LOGGER.debug("Roomba %s has no data yet. Skip update", self.name)
            return
        self._available = True
        self._battery_level = self.vacuum.get_battery_level()
        self._mission_name = None
        self._mission_state = None
        if self._mission_state == 'run':
            self._is_on = True
        else:
            self._is_on = False
