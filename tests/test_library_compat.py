"""Regression tests for the pinned smartmeter_austria_energy library."""

from Crypto.Cipher import AES
from smartmeter_austria_energy.decrypt import Decrypt
from smartmeter_austria_energy.supplier import SUPPLIERS, SUPPLIER_EVN_NAME

_KEY_HEX = "00112233445566778899AABBCCDDEEFF"
_DEVICE_NUMBER = b"123456789012"
_DEVICE_NUMBER_OBIS = b"\x00\x00\x60\x01\x00\xff"  # 0-0:96.1.0.255


def _evn_frames(plaintext: bytes) -> tuple[bytes, bytes]:
    """Encrypt plaintext and split it into EVN frames like the meter sends them."""
    supplier = SUPPLIERS[SUPPLIER_EVN_NAME]
    systitle = b"KFM\x10\x00\x00\x00\x01"
    invocation_counter = b"\x00\x00\x00\x2a"

    header1 = bytearray(supplier.enc_data_start_byte)
    header1[0:4] = supplier.frame1_start_bytes
    header1[11:19] = systitle
    header1[supplier.ic_start_byte : supplier.ic_start_byte + 4] = invocation_counter

    cipher = AES.new(
        bytes.fromhex(_KEY_HEX), AES.MODE_GCM, nonce=systitle + invocation_counter
    )
    encrypted = cipher.encrypt(plaintext)
    split = 200

    frame1 = bytes(header1) + encrypted[:split] + b"\x00\x16"
    frame2 = supplier.frame2_start_bytes + bytes(5) + encrypted[split:] + b"\x00\x16"
    return frame1, frame2


def test_evn_device_number_at_end_of_telegram():
    """EVN telegrams end with the device number and no trailing bytes.

    smartmeter_austria_energy 1.5.0 rejects such telegrams ("Not enough data to
    read the complete OctetString: expected end position 245 but total length
    is 243"), so EVN meters cannot be read with it. Keep this test when
    upgrading the library.
    """
    # 229 filler bytes, then OctetString marker, length 12 and the device number:
    # 243 bytes in total, as in the telegrams of real EVN meters.
    plaintext = bytes(229) + b"\x09\x0c" + _DEVICE_NUMBER
    assert len(plaintext) == 243

    frame1, frame2 = _evn_frames(plaintext)
    decrypt = Decrypt(SUPPLIERS[SUPPLIER_EVN_NAME], frame1, frame2, _KEY_HEX)
    decrypt.parse_all()

    assert decrypt.obis[_DEVICE_NUMBER_OBIS] == _DEVICE_NUMBER
