from typing import List, Optional

from dapp.db import (
    add_stream,
    delete_stream_by_id,
    get_user_shares,
    get_max_end_timestamp_for_wallet,
    get_stream_by_id,
    get_wallet_endend_streams,
    get_wallet_streams,
    get_token_total_assets,
    get_token_total_shares,
    set_token_total_assets,
    set_token_total_shares,
    set_users_shares,
    update_stream_accrued,
    update_stream_amount_duration,
    get_wallet_non_accrued_streamed_amts,
)
from dapp.hook import hook
from dapp.stream import Stream
from dapp.util import (
    address_or_raise,
    apply,
    assets_to_shares,
    process_streams_before,
    shares_to_assets,
    with_checksum_address,
)


@apply(with_checksum_address)
class StreamRebaseToken:
    def __init__(self, connection, address: str):
        self._connection = connection
        self._address = address

    def get_address(self) -> str:
        return self._address

    def get_stored_balance(self, wallet: str):
        shares = get_user_shares(self._connection, wallet, self._address)
        total_assets = get_token_total_assets(self._connection, self._address)
        total_shares = get_token_total_shares(self._connection, self._address)
        return shares_to_assets(shares, total_shares, total_assets)

    def set_stored_user_shares(self, wallet: str, shares: int):
        return set_users_shares(self._connection, wallet, self._address, shares)

    def get_wallet_endend_streams(
        self, wallet: str, current_timestamp: int
    ) -> List[Stream]:
        return get_wallet_endend_streams(
            self._connection, wallet, self._address, current_timestamp
        )

    def set_stream_accrued(self, stream_id: int):
        return update_stream_accrued(self._connection, stream_id, True)

    def get_stream_by_id(self, stream_id: int) -> Stream:
        return get_stream_by_id(self._connection, stream_id)

    def add_stream(self, stream: Stream) -> int:
        return add_stream(self._connection, stream)

    def get_stored_total_supply(self):
        return get_token_total_assets(self._connection, self._address)

    def process_streams(self, account_address: str, current_timestamp: int):
        ended_streams = self.get_wallet_endend_streams(
            account_address, current_timestamp
        )

        balance = self.get_stored_balance(account_address)
        total_assets = get_token_total_assets(self._connection, self._address)
        total_shares = get_token_total_shares(self._connection, self._address)
        for stream in ended_streams:
            self.set_stream_accrued(stream.id)
            streamed_amount = stream.streamed_amt(current_timestamp)
            if stream.from_address == account_address:
                balance -= streamed_amount
                balance_to = (
                    self.get_stored_balance(stream.to_address) + streamed_amount
                )
                shares = assets_to_shares(balance_to, total_shares, total_assets)
                self.set_stored_user_shares(stream.to_address, shares)
            if stream.to_address == account_address:
                balance += streamed_amount
                balance_from = (
                    self.get_stored_balance(stream.from_address) - streamed_amount
                )
                shares = assets_to_shares(balance_from, total_shares, total_assets)
                self.set_stored_user_shares(stream.from_address, shares)

        shares = assets_to_shares(balance, total_shares, total_assets)
        self.set_stored_user_shares(account_address, shares)

        hook(self._connection, self._address, account_address, current_timestamp)

    def mint_shares(self, shares_amount: int, wallet: str):
        address_or_raise(wallet)
        if shares_amount <= 0:
            raise ValueError("Shares amount must be positive.")
        total_shares = get_token_total_shares(self._connection, self._address)
        new_total_shares = total_shares + shares_amount
        set_token_total_shares(self._connection, self._address, new_total_shares)
        current_user_shares = get_user_shares(self._connection, wallet, self._address)
        new_user_shares = current_user_shares + shares_amount
        self.set_stored_user_shares(wallet, new_user_shares)

    def mint_assets(self, assets_amount: int, wallet: str):
        address_or_raise(wallet)
        if assets_amount <= 0:
            raise ValueError("Asset amount must be positive.")
        total_assets = get_token_total_assets(self._connection, self._address)
        total_shares = get_token_total_shares(self._connection, self._address)

        if total_assets == 0:
            new_shares = assets_amount
        else:
            new_shares = assets_to_shares(assets_amount, total_shares, total_assets)
        new_total_assets = total_assets + assets_amount
        set_token_total_assets(self._connection, self._address, new_total_assets)

        self.mint_shares(new_shares, wallet)

    def rebase(self, new_total_assets: int):
        set_token_total_assets(self._connection, self._address, new_total_assets)

    @process_streams_before
    def burn_shares(self, amount: int, sender: str, current_timestamp: int):
        assert current_timestamp is not None, "Current timestamp must be provided."
        assert amount > 0, "Amount must be positive."

        current_user_shares = get_user_shares(self._connection, sender, self._address)
        new_user_shares = current_user_shares - amount
        self.set_stored_user_shares(sender, new_user_shares)

    @process_streams_before
    def burn_assets(self, assets_amount: int, sender: str, current_timestamp: int):
        assert current_timestamp is not None, "Current timestamp must be provided."
        assert assets_amount > 0, "Asset amount must be positive."

        total_assets = get_token_total_assets(self._connection, self._address)
        total_shares = get_token_total_shares(self._connection, self._address)
        user_shares = get_user_shares(self._connection, sender, self._address)

        # Calculate the shares to burn
        shares_to_burn = assets_to_shares(assets_amount, total_shares, total_assets)

        assert (
            shares_to_burn <= user_shares
        ), "Not enough shares to burn the requested assets."

        # Update user's shares
        new_user_shares = user_shares - shares_to_burn
        self.set_stored_user_shares(sender, new_user_shares)

        # Update token's total assets and total shares
        new_total_assets = total_assets - assets_amount
        new_total_shares = total_shares - shares_to_burn
        set_token_total_assets(self._connection, self._address, new_total_assets)
        set_token_total_shares(self._connection, self._address, new_total_shares)

    def balance_of(
        self,
        account_address: str,
        at_timestamp: int,
        count_received=True,
        recipient_until_timestamp=0,
    ):
        address_or_raise(account_address)
        balance = self.get_stored_balance(account_address)
        streamed_amounts = get_wallet_non_accrued_streamed_amts(
            self._connection,
            account_address,
            self._address,
            at_timestamp,
            recipient_until_timestamp=(
                at_timestamp if count_received else recipient_until_timestamp
            ),
        )

        balance += sum(streamed for streamed in streamed_amounts)

        return balance

    # Only used in the indexer and never during dapp execution
    def future_balance_of(self, account_address: str, future_timestamp=None):
        address_or_raise(account_address)
        self._connection.execute("SAVEPOINT future_balance_of")
        try:
            max_timestamp = (
                future_timestamp
                if future_timestamp
                else get_max_end_timestamp_for_wallet(self._connection, account_address)
            )
            hook(self._connection, self._address, account_address, max_timestamp)
            balance = self.balance_of(account_address, max_timestamp)
        finally:
            self._connection.execute("ROLLBACK TO SAVEPOINT future_balance_of")
            self._connection.execute("RELEASE SAVEPOINT future_balance_of")

        return balance

    def get_streams(self, account_address: str):
        address_or_raise(account_address)
        return get_wallet_streams(self._connection, account_address, self._address)

    # Only used in the indexer and never during dapp execution
    def future_get_streams(self, account_address: str, future_timestamp=None):
        address_or_raise(account_address)
        self._connection.execute("SAVEPOINT future_get_streams")
        try:
            max_timestamp = (
                future_timestamp
                if future_timestamp
                else get_max_end_timestamp_for_wallet(self._connection, account_address)
            )
            hook(self._connection, self._address, account_address, max_timestamp)
            streams = self.get_streams(account_address)
        finally:
            self._connection.execute("ROLLBACK TO SAVEPOINT future_get_streams")
            self._connection.execute("RELEASE SAVEPOINT future_get_streams")

        return streams

    def _transfer(
        self,
        receiver: str,
        amount: int,
        duration: int,
        start_timestamp: int,
        sender: str,
        current_timestamp: int,
        swap_id: Optional[int] = None,
    ) -> int:
        address_or_raise(receiver)
        start_timestamp = current_timestamp if start_timestamp == 0 else start_timestamp
        assert (
            start_timestamp >= current_timestamp
        ), "Start timestamp must be in the future."
        assert duration >= 0, "Duration must be positive."
        assert sender != receiver, "Sender and receiver must be different."
        assert amount >= 0, "Amount must be positive."

        max_timestamp = max(
            start_timestamp + duration,
            get_max_end_timestamp_for_wallet(self._connection, sender),
        )

        future_balance_after_send = self.balance_of(
            sender, max_timestamp, False, current_timestamp
        )
        assert future_balance_after_send >= amount, "Not enough funds for the transfer."

        return self.add_stream(
            Stream(
                stream_id="",
                from_address=sender,
                to_address=receiver,
                start_timestamp=start_timestamp,
                duration=duration,
                amount=amount,
                token_address=self.get_address(),
                accrued=False,
                swap_id=swap_id,
            )
        )

    @process_streams_before
    def transfer(
        self,
        receiver: str,
        amount: int,
        duration: int,
        start_timestamp: int,
        sender: str,
        current_timestamp: int,
        swap_id: Optional[int] = None,
    ) -> int:
        return self._transfer(
            receiver,
            amount,
            duration,
            start_timestamp,
            sender,
            current_timestamp,
            swap_id,
        )

    @process_streams_before
    def cancel_stream(self, stream_id: int, sender: str, current_timestamp: int):
        stream = self.get_stream_by_id(stream_id)
        assert stream is not None, "Stream not found."
        assert stream.from_address == sender, "Sender is not the stream owner."
        assert (
            stream.start_timestamp + stream.duration >= current_timestamp
        ), "Stream is already completed."

        if stream.start_timestamp > current_timestamp:
            delete_stream_by_id(self._connection, stream_id)
        else:
            streamed = stream.streamed_amt(current_timestamp)
            update_stream_amount_duration(
                self._connection,
                stream_id,
                current_timestamp - stream.start_timestamp,
                streamed,
            )
