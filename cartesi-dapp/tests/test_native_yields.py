import json
from typing import Any, Dict, List
import os

os.environ["ROLLUP_HTTP_SERVER_URL"] = "http://127.0.0.1:8080/host-runner"
import unittest
from unittest.mock import MagicMock, Mock, patch
import sys
from eth_abi import encode
import secrets
from eth_utils import to_checksum_address

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from dapp.db import get_connection, get_dapp_addresses, get_admin
from dapp.streamrebasetoken import StreamRebaseToken
from sqlite import initialise_db
from tests.utils import calculate_total_supply_token
from dapp.handlers import handle_action

# {'metadata': {'msg_sender': '0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266', 'epoch_index': 0, 'input_index': 1, 'block_number': 30334, 'timestamp': 1722152540}, 'payload': '0xdeadbeef'}


def hex_to_bytes(hex_string: str) -> bytes:
    # Remove '0x' prefix if present
    hex_string = hex_string.removeprefix("0x")
    return bytes.fromhex(hex_string)


def generate_random_address():
    # Generate 20 random bytes (160 bits)
    random_bytes = secrets.token_bytes(20)

    # Convert to a hexadecimal string and add '0x' prefix
    hex_address = "0x" + random_bytes.hex()

    # Convert to checksum address
    return to_checksum_address(hex_address)


def format_yield_bridge_input(
    token_address: str, dapp_address: str, amount: int, recipient: str, data: str
) -> str:
    encoded = encode(
        ["address", "address", "uint256", "address", "bytes"],
        [token_address, dapp_address, amount, recipient, hex_to_bytes(data)],
    )
    return "0x" + encoded.hex()


def format_json_data(method: str, args: Dict[str, Any]) -> str:
    data = {
        "method": method,
        "args": {
            key: str(value) if isinstance(value, (int, float)) else value
            for key, value in args.items()
        },
    }

    # Convert the dictionary to a JSON string
    json_string = json.dumps(data)

    # Encode the JSON string to bytes and then to hex
    return "0x" + json_string.encode("utf-8").hex()


def encode_input_box_wrapper_input(
    sender_address: str,
    token_addresses: List[str],
    amounts: List[int],
    data: str,
) -> str:
    encoded = encode(
        ["address", "address[]", "uint256[]", "bytes"],
        [sender_address, token_addresses, amounts, hex_to_bytes(data)],
    )
    return "0x" + encoded.hex()


class TestNativeYields(unittest.TestCase):
    def setUp(self):
        os.environ["DB_FILE_PATH"] = "test-dapp.sqlite"
        os.environ["ROLLUP_HTTP_SERVER_URL"] = "http://127.0.0.1:8080/host-runner"
        initialise_db()
        self.connection = get_connection()
        self.mock_post = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"key": "value"}  # Mocked response
        self.mock_post.return_value = mock_response
        requests.post = self.mock_post

        self.token_address = generate_random_address()
        self.sender_address = generate_random_address()
        self.receiver_address = generate_random_address()
        self.random_address = generate_random_address()
        self.random_address_2 = generate_random_address()

        self.token = StreamRebaseToken(self.connection, self.token_address)

    def tearDown(self):
        token = StreamRebaseToken(self.connection, self.token_address)
        calculated_supply = calculate_total_supply_token(
            self.connection, self.token_address
        )
        total_supply = token.get_stored_total_supply()
        self.assertEqual(
            calculated_supply,
            total_supply,
            "Total supply is not equal to calculated supply.",
        )

    def claim_admin(self, address: str):
        set_admin_input = format_json_data(
            "claim_admin",
            {"admin": address},
        )

        input_box_wrapper_input = encode_input_box_wrapper_input(
            address,
            [],
            [],
            set_admin_input,
        )

        data = {
            "metadata": {
                "msg_sender": address,
                "epoch_index": 0,
                "input_index": 1,
                "block_number": 30334,
                "timestamp": 1722152540,
            },
            "payload": input_box_wrapper_input,
        }
        handle_action(data, self.connection)

    def set_input_box_wrapper(self, address: str, from_address: str):
        set_input_box_wrapper_input = format_json_data(
            "set_input_box_wrapper",
            {"input_box_wrapper": address},
        )

        input_box_wrapper_input = encode_input_box_wrapper_input(
            from_address,
            [],
            [],
            set_input_box_wrapper_input,
        )

        data = {
            "metadata": {
                "msg_sender": from_address,
                "epoch_index": 0,
                "input_index": 1,
                "block_number": 30334,
                "timestamp": 1722152540,
            },
            "payload": input_box_wrapper_input,
        }
        handle_action(data, self.connection)

    def set_yield_bridge(self, address: str, from_address: str):
        set_yield_bridge_input = format_json_data(
            "set_yield_bridge",
            {"yield_bridge": address},
        )

        input_box_wrapper_input = encode_input_box_wrapper_input(
            from_address,
            [],
            [],
            set_yield_bridge_input,
        )

        data = {
            "metadata": {
                "msg_sender": from_address,
                "epoch_index": 0,
                "input_index": 1,
                "block_number": 30334,
                "timestamp": 1722152540,
            },
            "payload": input_box_wrapper_input,
        }
        handle_action(data, self.connection)

    def test_initialization(self):
        total_supply = self.token.get_stored_total_supply()
        self.assertEqual(total_supply, 0, "Initial total supply should be zero.")

    def test_claim_admin(self):

        input_box_wrapper_address = generate_random_address()
        self.claim_admin(self.sender_address)
        self.set_input_box_wrapper(input_box_wrapper_address, self.sender_address)
        self.set_yield_bridge(self.sender_address, self.sender_address)
        admin_address = get_admin(self.connection)
        self.assertEqual(
            admin_address, self.sender_address, "Admin address should be the sender."
        )

    def test_deposit(self):
        deposit_amount = 1000000000000000000
        deposit_time = 1722152540
        dapp_address = generate_random_address()
        input_box_wrapper_address = generate_random_address()
        yield_bridge_address = generate_random_address()
        self.claim_admin(self.sender_address)
        self.set_input_box_wrapper(input_box_wrapper_address, self.sender_address)
        self.set_yield_bridge(yield_bridge_address, self.sender_address)

        yield_bridge_input = format_yield_bridge_input(
            self.token_address,
            dapp_address,
            deposit_amount,
            self.receiver_address,
            "0x",
        )

        input_box_wrapper_input = encode_input_box_wrapper_input(
            yield_bridge_address,
            [],
            [],
            yield_bridge_input,
        )

        data = {
            "metadata": {
                "msg_sender": input_box_wrapper_address,
                "epoch_index": 0,
                "input_index": 1,
                "block_number": 30334,
                "timestamp": deposit_time,
            },
            "payload": input_box_wrapper_input,
        }
        handle_action(data, self.connection)

        balance = StreamRebaseToken(self.connection, self.token_address).balance_of(
            self.receiver_address, deposit_time
        )
        self.assertEqual(balance, deposit_amount, "Balance should be 1.")


if __name__ == "__main__":
    unittest.main()
