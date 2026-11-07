"""Config flow for Smart meter integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
import os
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo
from smartmeter_austria_energy.exceptions import SmartmeterException
from smartmeter_austria_energy.smartmeter import Smartmeter
from smartmeter_austria_energy.supplier import SUPPLIERS
import voluptuous as vol

from .const import (
    CONF_COM_PORT,
    CONF_KEY_HEX,
    CONF_SERIAL_NO,
    CONF_SUPPLIER_NAME,
    DOMAIN,
    OPT_DATA_INTERVAL,
    OPT_DATA_INTERVAL_VALUE,
)

_LOGGER = logging.getLogger(__name__)

SERIAL_BY_ID_DIR = "/dev/serial/by-id"


def validate_and_connect(data: Mapping[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    com_port = data[CONF_COM_PORT]
    supplier_name = data[CONF_SUPPLIER_NAME]
    key_hex = data[CONF_KEY_HEX]

    _LOGGER.debug("Initialising com port=%s", com_port)
    ret = {}
    try:
        supplier = SUPPLIERS.get(supplier_name)
        adapter = Smartmeter(supplier, com_port, key_hex)
        obisdata = adapter.read()

        device_number = obisdata.DeviceNumber.value
        ret["title"] = f"Smart Meter '{device_number}'"
        ret["device_number"] = device_number
        _LOGGER.debug("Returning device info=%s", ret)
    except SmartmeterException as err:
        _LOGGER.warning("Could not connect to device=%s", com_port)
        raise err

    # Return info we want to store in the config entry.
    return ret


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id link pointing to the given device, if one exists.

    By-id paths contain the USB vendor, product and serial number of the adapter and
    therefore stay the same after a reboot or when other USB devices are plugged in,
    unlike /dev/ttyUSBx which is assigned in order of detection.
    """
    by_id = SERIAL_BY_ID_DIR
    if not os.path.isdir(by_id):
        return dev_path

    real_dev_path = os.path.realpath(dev_path)
    for entry in sorted(os.scandir(by_id), key=lambda e: e.name):
        if os.path.realpath(entry.path) == real_dev_path:
            return entry.path
    return dev_path


def _port_label(port: ListPortInfo, path: str) -> str:
    """Build a human readable label for a serial port."""
    details = [
        part
        for part in (port.description, port.manufacturer)
        if part and part != "n/a"
    ]
    if port.serial_number:
        details.append(f"s/n: {port.serial_number}")
    if path != port.device:
        details.append(port.device)
    if details:
        return f"{path} - {' - '.join(dict.fromkeys(details))}"
    return path


def scan_comports() -> tuple[list[SelectOptionDict] | None, str | None]:
    """Find available com ports for the GUI dropdown.

    The stable /dev/serial/by-id path is used as value whenever it is available.
    """
    com_ports = serial.tools.list_ports.comports()
    com_ports_list: list[SelectOptionDict] = []
    for port in com_ports:
        path = get_serial_by_id(port.device)
        com_ports_list.append(
            SelectOptionDict(value=path, label=_port_label(port, path))
        )
        _LOGGER.debug("COM port option: %s", path)
    if len(com_ports_list) > 0:
        return com_ports_list, com_ports_list[0]["value"]
    _LOGGER.warning(
        "No com ports found.  Need a valid M-BUS to USB device to communicate"
    )
    return None, None


def _com_port_selector(options: list[SelectOptionDict]) -> SelectSelector:
    """Return the selector used to choose the com port."""
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=True,
        )
    )


class SmartmeterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the smart meters."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self.config = None
        self._com_ports_list = None
        self._default_com_port = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialised by the user."""

        errors = {}
        if self._com_ports_list is None:
            result = await self.hass.async_add_executor_job(scan_comports)
            self._com_ports_list, self._default_com_port = result
            if self._default_com_port is None:
                return self.async_abort(reason="no_serial_ports")

        # Handle the initial step.
        if user_input is not None:
            try:
                info = await self.hass.async_add_executor_job(
                    validate_and_connect, user_input
                )

            except SmartmeterException:
                return self.async_abort(reason="cannot_connect")
            else:
                info.update(user_input)

                device_unique_id = info["device_number"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_SUPPLIER_NAME: user_input[CONF_SUPPLIER_NAME],
                        CONF_COM_PORT: user_input[CONF_COM_PORT],
                        CONF_KEY_HEX: user_input[CONF_KEY_HEX],
                        CONF_SERIAL_NO: device_unique_id,
                    },
                )

        # If no user input, must be first pass through the config.  Show  initial form.
        suppliers = list(SUPPLIERS.keys())
        default_supplier = suppliers[0]

        config_options = {
            vol.Required(CONF_SUPPLIER_NAME, default=default_supplier): SelectSelector(
                SelectSelectorConfig(
                    options=suppliers, mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                CONF_COM_PORT, default=self._default_com_port
            ): _com_port_selector(self._com_ports_list),
            vol.Required(CONF_KEY_HEX): str,
        }
        schema = vol.Schema(config_options)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SmartMeterOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SmartMeterOptionsFlowHandler()


class SmartMeterOptionsFlowHandler(OptionsFlow):
    """Defines the configurable options for a smart meter."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options (com port and update interval)."""
        _errors: dict[str, str] = {}
        current_port = self.config_entry.data.get(CONF_COM_PORT)

        if user_input is not None:
            new_data_interval = user_input.get(OPT_DATA_INTERVAL)
            new_port = user_input.get(CONF_COM_PORT) or current_port
            _LOGGER.debug("New data interval was set to %s", new_data_interval)

            if new_data_interval is None:
                _LOGGER.debug("New data interval is none")
                _errors["base"] = "data_interval_empty"

            elif not 5 <= new_data_interval <= 3600:
                _LOGGER.debug("New data interval is wrong (out of limits)")
                _errors["base"] = "data_interval_wrong"

            elif new_port != current_port:
                _errors = await self._async_validate_port(new_port)

            if not _errors:
                new_options = {
                    **self.config_entry.options,
                    OPT_DATA_INTERVAL: new_data_interval,
                }
                # Store port in the entry data and the options in one update, so
                # the entry is reloaded only once.
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_COM_PORT: new_port},
                    options=new_options,
                )
                return self.async_create_entry(title="", data=new_options)

        com_ports_list, _ = await self.hass.async_add_executor_job(scan_comports)
        com_ports_list = list(com_ports_list or [])
        default_port = current_port
        if current_port:
            # Offer the stable by-id path for the configured device if it exists.
            by_id_port = await self.hass.async_add_executor_job(
                get_serial_by_id, current_port
            )
            if any(option["value"] == by_id_port for option in com_ports_list):
                default_port = by_id_port
            elif not any(
                option["value"] == current_port for option in com_ports_list
            ):
                com_ports_list.insert(
                    0, SelectOptionDict(value=current_port, label=current_port)
                )

        schema: dict[Any, Any] = {}
        if com_ports_list:
            schema[vol.Required(CONF_COM_PORT, default=default_port)] = (
                _com_port_selector(com_ports_list)
            )
        schema[
            vol.Optional(
                OPT_DATA_INTERVAL,
                default=self.config_entry.options.get(
                    OPT_DATA_INTERVAL, OPT_DATA_INTERVAL_VALUE
                ),
            )
        ] = int

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=_errors,
        )

    async def _async_validate_port(self, new_port: str) -> dict[str, str]:
        """Check that the smart meter of this entry can be read on the new port."""
        if os.path.realpath(new_port) == os.path.realpath(
            self.config_entry.data.get(CONF_COM_PORT, "")
        ):
            # Same device, e.g. switched from /dev/ttyUSB0 to its by-id link.
            return {}

        try:
            info = await self.hass.async_add_executor_job(
                validate_and_connect,
                {**self.config_entry.data, CONF_COM_PORT: new_port},
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Could not read smart meter on port %s", new_port)
            return {"base": "cannot_connect"}

        expected = self.config_entry.data.get(CONF_SERIAL_NO)
        if expected and info.get("device_number") != expected:
            _LOGGER.warning(
                "Port %s belongs to smart meter %s, expected %s",
                new_port,
                info.get("device_number"),
                expected,
            )
            return {"base": "wrong_device"}
        return {}
