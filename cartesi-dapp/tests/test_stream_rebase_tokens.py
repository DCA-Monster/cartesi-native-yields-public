import os
import unittest
from unittest.mock import MagicMock, Mock, patch
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from dapp.db import get_connection, get_token_total_assets, get_token_total_shares
from dapp.streamrebasetoken import StreamRebaseToken
from sqlite import initialise_db
from tests.utils import calculate_total_supply_token


class TestStreamRebaseToken(unittest.TestCase):
    def setUp(self):
        os.environ["DB_FILE_PATH"] = "test-dapp.sqlite"
        initialise_db()
        self.connection = get_connection()
        self.mock_post = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"key": "value"}  # Mocked response
        self.mock_post.return_value = mock_response
        requests.post = self.mock_post

        self.token_address = "0x1234567890AbcdEF1234567890ABCDEF12345673"
        self.sender_address = "0x1234567890ABCDEF1234567890ABCDEF12345672"
        self.receiver_address = "0xabCDEF1234567890ABcDEF1234567890aBCDeF12"
        self.random_address = "0x1234567890ABCDEF1234567890ABCDEF12345670"
        self.random_address_2 = "0x1234567890ABCDEF1234567890ABCDEF12345671"

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

    def test_initialization(self):
        total_supply = self.token.get_stored_total_supply()
        self.assertEqual(total_supply, 0, "Initial total supply should be zero.")

    def test_minting_tokens(self):
        mint_amount = 1000
        self.token.mint_assets(mint_amount, self.sender_address)
        balance = self.token.get_stored_balance(self.sender_address)
        self.assertEqual(balance, mint_amount, "Minted amount does not match balance.")

        # mint for another user
        mint_amount_receiver = 1000
        self.token.mint_assets(mint_amount_receiver, self.receiver_address)
        balance = self.token.get_stored_balance(self.receiver_address)
        self.assertEqual(
            balance, mint_amount_receiver, "Minted amount does not match balance."
        )

        # check that sender's balance is not affected
        balance = self.token.get_stored_balance(self.sender_address)
        self.assertEqual(balance, mint_amount, "Sender's balance is not zero.")

    def test_minting_negative_amount(self):
        # Test minting a negative amount (should raise an exception)
        with self.assertRaises(ValueError):
            self.token.mint_assets(-100, self.sender_address)
        with self.assertRaises(ValueError):
            self.token.mint_shares(-100, self.sender_address)

    def test_burning_tokens(self):
        # Test burning tokens
        current_timestamp = 100
        mint_amount = 1000
        burn_amount = 1000
        self.token.mint_assets(mint_amount, self.sender_address)
        self.token.burn_assets(
            assets_amount=burn_amount,
            sender=self.sender_address,
            current_timestamp=current_timestamp,
        )  # Assuming current_timestamp is 100
        balance = self.token.balance_of(self.sender_address, current_timestamp)
        total_supply = self.token.get_stored_total_supply()
        self.assertEqual(
            balance, mint_amount - burn_amount, "Balance after burn is incorrect."
        )
        self.assertEqual(
            total_supply,
            mint_amount - burn_amount,
            "Total supply after burn is incorrect.",
        )
        total_shares = get_token_total_shares(self.connection, self.token_address)
        total_assets = get_token_total_assets(self.connection, self.token_address)
        self.assertEqual(total_shares, 0, "Total shares should be zero.")
        self.assertEqual(total_assets, 0, "Total assets should be zero.")

    def test_burning_more_than_balance(self):
        # Test burning more than the account's balance (should raise an exception)
        mint_amount = 100
        self.token.mint_assets(mint_amount, self.sender_address)
        with self.assertRaises(AssertionError):
            self.token.burn_assets(
                assets_amount=mint_amount + 1,
                sender=self.sender_address,
                current_timestamp=100,
            )

    def test_transfer_from(self):
        amount = 100
        duration = 0
        current_timestamp = 0
        start_timestamp = 0

        self.token.mint_assets(100, self.sender_address)

        self.token.transfer(
            receiver=self.receiver_address,
            amount=amount,
            duration=duration,
            start_timestamp=start_timestamp,
            sender=self.sender_address,
            current_timestamp=current_timestamp,
        )

        self.assertEqual(
            self.token.balance_of(self.sender_address, current_timestamp),
            0,
        )
        self.assertEqual(
            self.token.balance_of(self.receiver_address, current_timestamp),
            amount,
        )
        self.assertEqual(
            self.token.get_stored_total_supply(),
            amount,
        )

    def test_transfer_from_stream(self):
        amount = 100
        duration = 1000
        current_timestamp = 0
        start_timestamp = 0

        self.token.mint_assets(100, self.sender_address)

        self.assertEqual(
            self.token.get_stored_balance(self.sender_address),
            amount,
        )
        self.assertEqual(
            self.token.get_stored_total_supply(),
            amount,
        )
        # Transfer tokens in stream
        stream_id = self.token.transfer(
            receiver=self.receiver_address,
            amount=amount,
            duration=duration,
            start_timestamp=start_timestamp,
            sender=self.sender_address,
            current_timestamp=current_timestamp,
        )

        # After half the duration, the receiver should have half the amount of tokens and the sender the other half
        self.assertEqual(
            self.token.balance_of(
                self.receiver_address, current_timestamp + duration / 2
            ),
            amount / 2,
        )

        self.assertEqual(
            self.token.balance_of(
                self.sender_address, current_timestamp + duration / 2
            ),
            amount / 2,
        )

        # After the duration, the receiver should have all the tokens and the sender none
        self.assertEqual(
            self.token.balance_of(self.receiver_address, current_timestamp + duration),
            amount,
        )

        self.assertEqual(
            self.token.balance_of(self.sender_address, current_timestamp + duration),
            0,
        )

    def test_transfer_more_than_balance(self):
        current_timestamp = 0
        start_timestamp = 0
        duration = 1000
        amount = 100

        self.token.mint_assets(amount, self.sender_address)

        # Transfering more than the balance should raise an exception
        self.connection.execute("SAVEPOINT before_exception")
        with self.assertRaises(Exception) as context:
            try:
                self.token.transfer(
                    receiver=self.receiver_address,
                    amount=amount * 2,
                    duration=duration,
                    start_timestamp=start_timestamp,
                    sender=self.sender_address,
                    current_timestamp=current_timestamp,
                )
            except Exception as e:
                self.exception = e
                assert (
                    e.args[0]
                    == "Insufficient future balance to transfer. Check your streams."
                )
                self.connection.execute("ROLLBACK TO SAVEPOINT before_exception")
                self.connection.execute("RELEASE SAVEPOINT before_exception")
                raise e

        # Send half the amount
        self.token.transfer(
            receiver=self.receiver_address,
            amount=amount / 2,
            duration=duration,
            start_timestamp=start_timestamp,
            sender=self.sender_address,
            current_timestamp=current_timestamp,
        )

        # Simulate the passage of half the duration
        current_timestamp += duration / 2

        self.connection.execute("SAVEPOINT before_exception")
        with self.assertRaises(Exception) as context:
            try:
                self.token.transfer(
                    receiver=self.receiver_address,
                    amount=amount / 2 + 1,  # Send more than the remaining balance
                    duration=duration,
                    start_timestamp=current_timestamp
                    + 100,  # Start timestamp is in the future
                    sender=self.sender_address,
                    current_timestamp=current_timestamp,
                )
            except Exception as e:
                self.exception = e

                assert (
                    e.args[0]
                    == "Insufficient future balance to transfer. Check your streams."
                )
                self.connection.execute("ROLLBACK TO SAVEPOINT before_exception")
                self.connection.execute("RELEASE SAVEPOINT before_exception")
                raise e

    def test_stream_with_zero_duration(self):
        # Test adding a stream with a duration of zero (should raise an exception)
        self.token.mint_assets(100, self.sender_address)

        self.token.transfer(
            receiver=self.receiver_address,
            amount=50,
            duration=0,
            start_timestamp=0,
            sender=self.sender_address,
            current_timestamp=0,
        )

        assert self.token.balance_of(self.receiver_address, 0) == 50
        assert self.token.balance_of(self.sender_address, 0) == 50

    def test_stream_with_long_duration(self):
        # Test adding a stream with a very long duration
        long_duration = 999999
        mint_amount = 1000
        self.token.mint_assets(mint_amount, self.sender_address)
        stream_id = self.token.transfer(
            receiver=self.receiver_address,
            amount=mint_amount,
            duration=long_duration,
            start_timestamp=0,
            sender=self.sender_address,
            current_timestamp=0,
        )
        self.assertTrue(isinstance(stream_id, int), "Stream ID should be an integer.")

    def test_invalid_addresses(self):
        # Test methods with invalid addresses
        with self.assertRaises(ValueError):
            self.token.mint_assets(100, "InvalidAddress")

    def test_maximum_integer_values(self):
        # Test behavior with maximum integer values
        max_int = 2**63 - 1
        self.token.mint_assets(max_int, self.sender_address)
        balance = self.token.get_stored_balance(self.sender_address)
        self.assertEqual(balance, max_int, "Balance with max int does not match.")

    def test_rebase(self):
        mint_amount = 1000
        self.token.mint_assets(mint_amount, self.sender_address)
        balance = self.token.get_stored_balance(self.sender_address)
        self.assertEqual(balance, mint_amount, "Minted amount does not match balance.")

        # mint for another user
        mint_amount_receiver = 500
        self.token.mint_assets(mint_amount_receiver, self.receiver_address)
        balance = self.token.get_stored_balance(self.receiver_address)
        self.assertEqual(
            balance, mint_amount_receiver, "Minted amount does not match balance."
        )

        # Rebase tokens increasing the supply from 1500 to 3000
        new_assets = 3000
        self.token.rebase(new_assets)

        self.assertEqual(
            self.token.get_stored_balance(self.sender_address),
            mint_amount * 2,
            "Rebase amount does not match balance.",
        )
        self.assertEqual(
            self.token.get_stored_balance(self.receiver_address),
            mint_amount_receiver * 2,
            "Rebase amount does not match balance.",
        )

        # Burn tokens
        self.token.burn_assets(
            assets_amount=self.token.balance_of(self.sender_address, 0),
            sender=self.sender_address,
            current_timestamp=0,
        )
        self.assertEqual(
            self.token.get_stored_balance(self.sender_address),
            0,
            "Burn amount does not match balance.",
        )


if __name__ == "__main__":
    unittest.main()
