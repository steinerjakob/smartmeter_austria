"""Test the config flow."""
from unittest.mock import patch

from homeassistant.config_entries import OptionsFlow
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from serial.tools import list_ports_common
from smartmeter_austria_energy.exceptions import SmartmeterException
from smartmeter_austria_energy.obisdata import ObisData, ObisValueBytes
from smartmeter_austria_energy.smartmeter import Smartmeter
from smartmeter_austria_energy.supplier import SUPPLIER_EVN_NAME

from custom_components.smartmeter_austria.config_flow import (
    SmartmeterConfigFlow,
    SmartMeterOptionsFlowHandler,
    get_serial_by_id,
    scan_comports,
)
from custom_components.smartmeter_austria.const import (
    CONF_COM_PORT,
    CONF_KEY_HEX,
    CONF_SERIAL_NO,
    CONF_SUPPLIER_NAME,
    DOMAIN,
    OPT_DATA_INTERVAL,
)

_COM_PORT = "/dev/ttyUSB1"
_SERIAL_NUMBER = "DEVICE_NUMBER"
_SUPPLIER_NAME = SUPPLIER_EVN_NAME
_HEX_KEY = "my_hex_key"


def test_smartmeter_config_flow_constructor():
    """Simple test for construction and initialization."""
    result_flow_handler = SmartmeterConfigFlow()

    assert isinstance(result_flow_handler, SmartmeterConfigFlow)


@pytest.mark.asyncio
async def test_smartmeter_config_flow_async_step_user_user_input_is_none(hass):
    """Tests the user step without valid user data."""
    result_flow_handler = SmartmeterConfigFlow()
    result_flow_handler.hass = hass

    my_flow_result = await result_flow_handler.async_step_user()

    assert my_flow_result["type"] == "form"
    assert my_flow_result["step_id"] == "user"
    assert my_flow_result["errors"] == {}


@pytest.mark.asyncio
async def test_smartmeter_config_flow_async_step_user_user_input_id_loaded_new_smartmeter(
    hass,
):
    """Tests the user step with user data and inverter is not configured yet."""
    result_flow_handler = SmartmeterConfigFlow()
    result_flow_handler.hass = hass

    data = {
        CONF_SUPPLIER_NAME: _SUPPLIER_NAME,
        CONF_COM_PORT: _COM_PORT,
        CONF_KEY_HEX: _HEX_KEY,
    }

    with patch("serial.tools.list_ports.comports") as comports_mock:
        com_port_info = list_ports_common.ListPortInfo(_COM_PORT, True)
        comports_result: list[list_ports_common.ListPortInfo] = [com_port_info]
        comports_mock.return_value = comports_result

        with patch.object(
            SmartmeterConfigFlow, "_async_current_entries"
        ) as current_entries_mock:
            current_entries_mock.return_value = {}
            with patch.object(Smartmeter, "read") as smartmeter_mock:
                with patch.object(ObisData, "DeviceNumber") as device_number_mock:
                    device_number_object = ObisValueBytes(_SERIAL_NUMBER)
                    device_number_mock.return_value = device_number_object

                    smartmeter_mock.return_value = device_number_mock

                    with patch(
                        "custom_components.smartmeter_austria.config_flow.SmartmeterConfigFlow.async_set_unique_id"
                    ):
                        my_flow_result = await result_flow_handler.async_step_user(
                            user_input=data
                        )

    assert my_flow_result["type"] == "create_entry"


@pytest.mark.asyncio
async def test_smartmeter_config_flow_async_step_user_user_input_id_other_smartmeter(
    hass,
):
    """Tests the user step with user data and other configured smart meter."""
    result_flow_handler = SmartmeterConfigFlow()
    result_flow_handler.hass = hass

    com_port2 = "/dev/ttyUSB3"

    data = {
        CONF_SUPPLIER_NAME: _SUPPLIER_NAME,
        CONF_COM_PORT: _COM_PORT,
        CONF_KEY_HEX: _HEX_KEY,
        CONF_SERIAL_NO: _SERIAL_NUMBER,
    }

    mock_config = MockConfigEntry(domain=DOMAIN, data=data)
    with patch("serial.tools.list_ports.comports") as comports_mock:
        com_port_info = list_ports_common.ListPortInfo(com_port2, True)
        comports_result: list[list_ports_common.ListPortInfo] = [com_port_info]
        comports_mock.return_value = comports_result

        with patch(
            "custom_components.smartmeter_austria.config_flow.SmartmeterConfigFlow._async_current_entries"
        ) as current_entries_mock:
            current_entries_mock.return_value = {mock_config}

            with patch.object(Smartmeter, "read") as smartmeter_mock:
                with patch.object(ObisData, "DeviceNumber") as device_number_mock:
                    device_number_object = ObisValueBytes(_SERIAL_NUMBER)
                    device_number_mock.return_value = device_number_object

                    smartmeter_mock.return_value = device_number_mock

                    with patch(
                        "custom_components.smartmeter_austria.config_flow.SmartmeterConfigFlow.async_set_unique_id"
                    ):
                        my_flow_result = await result_flow_handler.async_step_user(
                            user_input=data
                        )

    assert my_flow_result["type"] == "create_entry"


@pytest.mark.asyncio
async def test_smartmeter_config_flow_async_get_options_flow():
    """Tests the async_get_options_flow."""

    flow_handler = SmartmeterConfigFlow()
    options_flow = OptionsFlow()

    result = flow_handler.async_get_options_flow(options_flow)

    assert isinstance(result, SmartMeterOptionsFlowHandler)


@pytest.mark.asyncio
async def test_smart_meter_options_flow_handler_constructor():
    """Simple test for construction and initialization."""

    options_flow_handler = SmartMeterOptionsFlowHandler()

    assert isinstance(options_flow_handler, SmartMeterOptionsFlowHandler)


def _add_entry(hass, options=None) -> MockConfigEntry:
    """Add a config entry for the options flow tests."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=_SERIAL_NUMBER,
        data={
            CONF_SUPPLIER_NAME: _SUPPLIER_NAME,
            CONF_COM_PORT: _COM_PORT,
            CONF_KEY_HEX: _HEX_KEY,
            CONF_SERIAL_NO: _SERIAL_NUMBER,
        },
        options=options or {},
    )
    config_entry.add_to_hass(hass)
    return config_entry


def _comports(*devices: str) -> list[list_ports_common.ListPortInfo]:
    return [list_ports_common.ListPortInfo(device, True) for device in devices]


async def _init_options_flow(hass, config_entry, ports=(_COM_PORT,)):
    with patch("serial.tools.list_ports.comports", return_value=_comports(*ports)):
        return await hass.config_entries.options.async_init(config_entry.entry_id)


async def _configure_options_flow(hass, flow_id, user_input, ports=(_COM_PORT,)):
    with (
        patch("serial.tools.list_ports.comports", return_value=_comports(*ports)),
        patch.object(hass.config_entries, "async_reload", return_value=True),
    ):
        return await hass.config_entries.options.async_configure(
            flow_id, user_input=user_input
        )


@pytest.mark.asyncio
async def test_smart_meter_options_flow_handler_async_step_init_no_user_input(hass):
    """Tests the init step without user input shows port and interval."""
    config_entry = _add_entry(hass)

    my_flow_result = await _init_options_flow(hass, config_entry)

    assert my_flow_result["type"] == "form"
    assert my_flow_result["step_id"] == "init"
    assert my_flow_result["errors"] == {}
    schema_keys = {str(key) for key in my_flow_result["data_schema"].schema}
    assert schema_keys == {CONF_COM_PORT, OPT_DATA_INTERVAL}


@pytest.mark.asyncio
async def test_smart_meter_options_flow_handler_async_step_init_user_input(hass):
    """Tests the init step with valid user input and unchanged port."""
    config_entry = _add_entry(hass)
    flow = await _init_options_flow(hass, config_entry)

    my_flow_result = await _configure_options_flow(
        hass, flow["flow_id"], {CONF_COM_PORT: _COM_PORT, OPT_DATA_INTERVAL: 10}
    )

    assert my_flow_result["type"] == "create_entry"
    assert config_entry.options[OPT_DATA_INTERVAL] == 10
    assert config_entry.data[CONF_COM_PORT] == _COM_PORT


@pytest.mark.asyncio
async def test_smart_meter_options_flow_handler_change_port(hass):
    """Tests changing the com port to another port with the same smart meter."""
    new_port = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A1B2C3-if00-port0"
    config_entry = _add_entry(hass)
    flow = await _init_options_flow(hass, config_entry, ports=(_COM_PORT, new_port))

    with patch(
        "custom_components.smartmeter_austria.config_flow.validate_and_connect",
        return_value={"device_number": _SERIAL_NUMBER},
    ) as validate_mock:
        my_flow_result = await _configure_options_flow(
            hass, flow["flow_id"], {CONF_COM_PORT: new_port, OPT_DATA_INTERVAL: 30}
        )

    assert my_flow_result["type"] == "create_entry"
    assert validate_mock.call_args.args[0][CONF_COM_PORT] == new_port
    assert config_entry.data[CONF_COM_PORT] == new_port
    assert config_entry.data[CONF_KEY_HEX] == _HEX_KEY


@pytest.mark.asyncio
async def test_smart_meter_options_flow_handler_change_port_wrong_device(hass):
    """Tests that a port with another smart meter is rejected."""
    new_port = "/dev/ttyUSB7"
    config_entry = _add_entry(hass)
    flow = await _init_options_flow(hass, config_entry)

    with patch(
        "custom_components.smartmeter_austria.config_flow.validate_and_connect",
        return_value={"device_number": "OTHER"},
    ):
        my_flow_result = await _configure_options_flow(
            hass, flow["flow_id"], {CONF_COM_PORT: new_port, OPT_DATA_INTERVAL: 30}
        )

    assert my_flow_result["type"] == "form"
    assert my_flow_result["errors"] == {"base": "wrong_device"}
    assert config_entry.data[CONF_COM_PORT] == _COM_PORT


@pytest.mark.asyncio
async def test_smart_meter_options_flow_handler_change_port_cannot_connect(hass):
    """Tests that a port where the meter cannot be read is rejected."""
    new_port = "/dev/ttyUSB7"
    config_entry = _add_entry(hass)
    flow = await _init_options_flow(hass, config_entry)

    with patch(
        "custom_components.smartmeter_austria.config_flow.validate_and_connect",
        side_effect=SmartmeterException("boom"),
    ):
        my_flow_result = await _configure_options_flow(
            hass, flow["flow_id"], {CONF_COM_PORT: new_port, OPT_DATA_INTERVAL: 30}
        )

    assert my_flow_result["type"] == "form"
    assert my_flow_result["errors"] == {"base": "cannot_connect"}
    assert config_entry.data[CONF_COM_PORT] == _COM_PORT


@pytest.mark.asyncio
async def test_smart_meter_options_flow_handler_async_step_init_interval_empty(hass):
    """Tests the init step with empty interval data."""
    config_entry = _add_entry(hass)
    flow = await _init_options_flow(hass, config_entry)
    flow_handler = hass.config_entries.options._progress[flow["flow_id"]]

    with patch("serial.tools.list_ports.comports", return_value=_comports(_COM_PORT)):
        my_flow_result = await flow_handler.async_step_init(
            user_input={OPT_DATA_INTERVAL: None}
        )

    assert my_flow_result["type"] == "form"
    assert my_flow_result["step_id"] == "init"
    assert my_flow_result["errors"] == {"base": "data_interval_empty"}


@pytest.mark.asyncio
async def test_smart_meter_options_flow_handler_async_step_init_interval_wrong(hass):
    """Tests the init step with invalid interval data."""
    config_entry = _add_entry(hass)
    flow = await _init_options_flow(hass, config_entry)

    my_flow_result = await _configure_options_flow(
        hass, flow["flow_id"], {CONF_COM_PORT: _COM_PORT, OPT_DATA_INTERVAL: 1}
    )

    assert my_flow_result["type"] == "form"
    assert my_flow_result["step_id"] == "init"
    assert my_flow_result["errors"] == {"base": "data_interval_wrong"}


def test_get_serial_by_id(tmp_path):
    """Tests that a /dev/ttyUSBx device is mapped to its by-id link."""
    device = tmp_path / "ttyUSB0"
    device.touch()
    by_id = tmp_path / "by-id"
    by_id.mkdir()
    link = by_id / "usb-FTDI_FT232R_USB_UART_A1B2C3-if00-port0"
    link.symlink_to(device)

    with patch(
        "custom_components.smartmeter_austria.config_flow.SERIAL_BY_ID_DIR",
        str(by_id),
    ):
        assert get_serial_by_id(str(device)) == str(link)
        other = str(tmp_path / "ttyUSB1")
        assert get_serial_by_id(other) == other


def test_scan_comports_uses_by_id_path():
    """Tests that the dropdown offers the by-id path with a readable label."""
    port = list_ports_common.ListPortInfo("/dev/ttyUSB0", True)
    port.description = "FT232R USB UART"
    port.manufacturer = "FTDI"
    port.serial_number = "A1B2C3"
    by_id = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A1B2C3-if00-port0"

    with (
        patch("serial.tools.list_ports.comports", return_value=[port]),
        patch(
            "custom_components.smartmeter_austria.config_flow.get_serial_by_id",
            return_value=by_id,
        ),
    ):
        options, default = scan_comports()

    assert default == by_id
    assert options[0]["value"] == by_id
    assert "FTDI" in options[0]["label"]
    assert "A1B2C3" in options[0]["label"]
    assert "/dev/ttyUSB0" in options[0]["label"]
