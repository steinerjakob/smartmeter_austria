"""Test the component setup."""
from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryNotReady
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
)
from smartmeter_austria_energy.exceptions import SmartmeterSerialException
from smartmeter_austria_energy.obisdata import ObisData, ObisValueBytes
from smartmeter_austria_energy.supplier import SUPPLIER_EVN_NAME

from custom_components.smartmeter_austria.__init__ import (
    async_options_update_listener,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smartmeter_austria.const import (
    CONF_COM_PORT,
    CONF_KEY_HEX,
    CONF_SUPPLIER_NAME,
    DOMAIN,
)
from custom_components.smartmeter_austria.coordinator import SmartmeterDataCoordinator

_COM_PORT = "/dev/ttyUSB1"
_SUPPLIER_NAME = SUPPLIER_EVN_NAME
_HEX_KEY = "my_hex_key"


@pytest.mark.asyncio
async def test_async_setup_entry_config_not_ready(hass):
    """Test the integration setup with no connection to the smart meter throwing a ConfigEntryNotReady exception."""

    _data = {
        CONF_SUPPLIER_NAME: _SUPPLIER_NAME,
        CONF_COM_PORT: _COM_PORT,
        CONF_KEY_HEX: _HEX_KEY,
    }

    with pytest.raises(ConfigEntryNotReady):
        mock_integration(hass, MockModule(DOMAIN))

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="my_unique_test_id",
            data=_data,
        )

        config_entry.add_to_hass(hass)

        with patch("smartmeter_austria_energy.smartmeter.Smartmeter.read") as read_mock:
            read_mock.side_effect = SmartmeterSerialException()

            await async_setup_entry(hass, config_entry)


def _obis_data_mock(device_nr: str) -> MagicMock:
    """Return a mocked ObisData object with the given device number."""
    obis_data = MagicMock(spec=ObisData)
    obis_data.DeviceNumber = ObisValueBytes(device_nr.encode())
    return obis_data


@pytest.mark.asyncio
async def test_async_setup_entry_domain_not_loaded(hass):
    """Test the integration setup and install the domain."""

    _data = {
        CONF_SUPPLIER_NAME: _SUPPLIER_NAME,
        CONF_COM_PORT: _COM_PORT,
        CONF_KEY_HEX: _HEX_KEY,
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="my_unique_test_id",
        data=_data,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "smartmeter_austria_energy.smartmeter.Smartmeter.read",
        return_value=_obis_data_mock("test"),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result
    assert config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert config_entry.runtime_data.coordinator.config_entry is config_entry


@pytest.mark.asyncio
async def test_async_setup_entry_domain_loaded(hass):
    """Test the integration setup when the domain data already exists."""

    _data = {
        CONF_SUPPLIER_NAME: _SUPPLIER_NAME,
        CONF_COM_PORT: _COM_PORT,
        CONF_KEY_HEX: _HEX_KEY,
    }

    hass.data.setdefault(DOMAIN, {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="my_unique_test_id",
        data=_data,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "smartmeter_austria_energy.smartmeter.Smartmeter.read",
        return_value=_obis_data_mock("test"),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.asyncio
async def test_async_unload_entry(hass):
    """Test to unlod the integration."""

    _data = {
        CONF_SUPPLIER_NAME: _SUPPLIER_NAME,
        CONF_COM_PORT: _COM_PORT,
        CONF_KEY_HEX: _HEX_KEY,
    }

    mock_integration(hass, MockModule(DOMAIN))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="my_unique_test_id",
        data=_data,
    )

    config_entry.add_to_hass(hass)

    with patch("smartmeter_austria_energy.smartmeter.Smartmeter") as smartmeter_mock:
        SmartmeterDataCoordinator(hass, adapter=smartmeter_mock)

        hass.data.setdefault(
            DOMAIN, {config_entry.entry_id: {}}
        )

        test_result = await async_unload_entry(hass, config_entry)
    assert test_result is True


@pytest.mark.asyncio
async def test_async_options_update_listener(hass):
    """Test the options update listener."""

    mock_integration(hass, MockModule(DOMAIN))

    _data = {
        CONF_SUPPLIER_NAME: _SUPPLIER_NAME,
        CONF_COM_PORT: _COM_PORT,
        CONF_KEY_HEX: _HEX_KEY,
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="my_unique_test_id",
        data=_data,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as method_mock:
        # act
        await async_options_update_listener(hass, config_entry)

        # assert
        method_mock.assert_called_once()
