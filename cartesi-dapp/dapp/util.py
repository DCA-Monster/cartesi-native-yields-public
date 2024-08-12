import json
import logging
import hashlib
from os import environ

# External libraries
from eth_abi.codec import ABICodec
from eth_abi.decoding import AddressDecoder, BooleanDecoder, UnsignedIntegerDecoder
from eth_abi.registry import BaseEquals, registry_packed
from eth_utils import is_hex_address, to_checksum_address, is_checksum_address

# Constants
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MINIMUM_LIQUIDITY = 100000
MAX_INT64 = 2**63 - 1
MAX_UINT256 = 2**256 - 1
USER_FEES = 30  # 0.3%
DCA_INTERVAL_SECONDS = 60
ONE_ETH = 10**18

CONDITION_TYPES = {"GT", "LT", "GTE", "LTE"}


# Custom Decoder Classes
class PackedBooleanDecoder(BooleanDecoder):
    data_byte_size = 1


class PackedAddressDecoder(AddressDecoder):
    data_byte_size = 20


# Registering Custom Decoders
registry_packed.register_decoder(BaseEquals("bool"), PackedBooleanDecoder, label="bool")
registry_packed.register_decoder(
    BaseEquals("address"), PackedAddressDecoder, label="address"
)
registry_packed.register_decoder(
    BaseEquals("uint"), UnsignedIntegerDecoder, label="uint"
)

# Codec for packed data
default_codec_packed = ABICodec(registry_packed)
decode_packed = default_codec_packed.decode


# Conversion utilities
def hex_to_str(hex_str):
    """Decode a hex string prefixed with "0x" into a UTF-8 string"""
    return bytes.fromhex(hex_str[2:]).decode("utf-8")


def str_to_hex(string):
    """Encode a string as a hex string, adding the "0x" prefix"""
    return "0x" + string.encode("utf-8").hex()


def str_to_int(string):
    """Converts a string to an integer. Returns 0 if conversion is not possible."""
    try:
        return int(string)
    except (TypeError, ValueError):
        return 0


def int_to_str(integer):
    """Converts an integer to a string. Returns '0' if the input is None or not an integer."""
    try:
        return str(int(integer))
    except (TypeError, ValueError):
        return "0"


# Decorators
def with_checksum_address(func):
    def wrapper(*args, **kwargs):
        new_args = tuple(
            to_checksum_address(arg) if is_hex_address(arg) else arg for arg in args
        )
        new_kwargs = {
            key: to_checksum_address(value) if is_hex_address(value) else value
            for key, value in kwargs.items()
        }
        return func(*new_args, **new_kwargs)

    return wrapper


def process_streams_before(func):
    def wrapper(self, *args, **kwargs):
        if not "current_timestamp" in kwargs or not "sender" in kwargs:
            raise ValueError("current_timestamp and sender must be provided.")
        current_timestamp = kwargs["current_timestamp"]
        sender = kwargs["sender"]

        self.process_streams(sender, current_timestamp)

        return func(self, *args, **kwargs)

    return wrapper


def apply(decorator):
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls

    return class_decorator


# Logging Configuration
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "message": record.msg,
            "level": record.levelname,
            "timestamp": record.created,
        }
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        return json.dumps(log_entry)


def assets_to_shares(assets_amount: int, total_shares: int, total_assets: int):
    if total_assets == 0:
        return 0
    return (assets_amount * total_shares) // total_assets


def shares_to_assets(shares_amount: int, total_shares: int, total_assets: int):
    if total_shares == 0:
        return 0
    return (shares_amount * total_assets) // total_shares


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Main code or configuration
rollup_server = environ.get("ROLLUP_HTTP_SERVER_URL", "http://127.0.0.1:5004")


# Utilities
def address_or_raise(address):
    if not is_checksum_address(address):
        raise ValueError(f"Invalid address {address}")
    return address
