import os
import sqlite3
from typing import List, Tuple
import unittest
from dapp.stream import Stream
from dapp.util import int_to_str, str_to_int, to_checksum_address
from dataclasses import dataclass


def get_connection():
    db_file_path = os.getenv("DB_FILE_PATH", "dapp.sqlite")
    conn = sqlite3.connect(db_file_path)
    # run only if not in a test unnitest
    if not unittest.TestCase.run:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
    return conn


def create_account_if_not_exists(connection, address):
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO account (address) VALUES (?)
        """,
        (address,),
    )


def create_token_if_not_exists(
    connection, token_address, default_total_assets=0, default_total_shares=0
):
    create_account_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO token (address, total_assets, total_shares)
        VALUES (?, ?, ?)
        """,
        (
            token_address,
            int_to_str(default_total_assets),
            int_to_str(default_total_shares),
        ),
    )


def create_pair_if_not_exists(
    connection, token_address, token_0_address, token_1_address
):
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO pair (address, token_0_address, token_1_address)
        VALUES (?, ?, ?)
        """,
        (token_address, token_0_address, token_1_address),
    )
    return cursor.lastrowid


def stream_from_row(row) -> Stream:
    return Stream(
        stream_id=row[0],
        from_address=row[1],
        to_address=row[2],
        start_timestamp=row[3],
        duration=row[4],
        amount=str_to_int(row[5]),
        token_address=row[6],
        accrued=True if row[7] == 1 else False,
        swap_id=row[8] if len(row) > 8 else None,
    )


def get_wallet_non_accrued_streamed_amts(
    connection,
    account_address,
    token_address,
    until_timestamp,
    recipient_until_timestamp=0,
):
    create_account_if_not_exists(connection, account_address)
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT start_timestamp, duration, amount, to_address
        FROM stream
        WHERE (from_address = ? OR to_address = ?) AND token_address = ? AND accrued = 0
        AND start_timestamp <= ?
        """,
        (account_address, account_address, token_address, until_timestamp),
    )

    for row in cursor:
        start_timestamp, duration, amount, to_address = row
        amount = int(amount)
        is_recipient = to_address == account_address
        effective_until = recipient_until_timestamp if is_recipient else until_timestamp

        if effective_until < start_timestamp:
            streamed_amount = 0
        elif effective_until >= start_timestamp + duration:
            streamed_amount = amount
        else:
            elapsed = effective_until - start_timestamp
            streamed_amount = (amount * elapsed) // duration

        yield (streamed_amount if is_recipient else -streamed_amount)


def get_wallet_streams(connection, account_address, token_address) -> List[Stream]:
    create_account_if_not_exists(connection, account_address)
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT * FROM stream
        WHERE (from_address = ? OR to_address = ?) AND token_address = ?
        """,
        (account_address, account_address, token_address),
    )
    rows = cursor.fetchall()

    streams = []
    for row in rows:
        streams.append(stream_from_row(row))

    return streams


def get_dapp_addresses(connection) -> Tuple[str, str, str]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT address FROM dapp_addresses
        WHERE name IN ('admin', 'input_box_wrapper', 'yield_bridge')
        ORDER BY CASE
            WHEN name = 'admin' THEN 1
            WHEN name = 'input_box_wrapper' THEN 2
            WHEN name = 'yield_bridge' THEN 3
        END
        """
    )
    rows = cursor.fetchall()
    if len(rows) != 3:
        raise ValueError("Not all required addresses are present in the database")
    return (rows[0][0], rows[1][0], rows[2][0])


def set_admin(connection, admin_address):
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE dapp_addresses
        SET address = ?
        WHERE name = 'admin'
        """,
        (admin_address,),
    )


def get_admin(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT address FROM dapp_addresses
        WHERE name = 'admin'
        """,
    )
    row = cursor.fetchone()
    return row[0] if row else None


def set_input_box_wrapper(connection, input_box_wrapper_address):
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE dapp_addresses
        SET address = ?
        WHERE name = 'input_box_wrapper'
        """,
        (input_box_wrapper_address,),
    )


def get_input_box_wrapper(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT address FROM dapp_addresses
        WHERE name = 'input_box_wrapper'
        """,
    )
    row = cursor.fetchone()
    return row[0] if row else None


def set_yield_bridge(connection, yield_bridge_address):
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE dapp_addresses
        SET address = ?
        WHERE name = 'yield_bridge'
        """,
        (yield_bridge_address,),
    )


def get_yield_bridge(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT address FROM dapp_addresses
        WHERE name = 'yield_bridge'
        """,
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_max_end_timestamp_for_wallet(connection, account_address):
    create_account_if_not_exists(connection, account_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT MAX(start_timestamp + duration)
        FROM stream
        WHERE (from_address = ? OR to_address = ?)
        """,
        (account_address, account_address),
    )

    result = cursor.fetchone()

    return result[0] if result[0] else 0


def get_wallet_endend_streams(
    connection, account_address, token_address, current_timestamp
) -> List[Stream]:
    create_account_if_not_exists(connection, account_address)
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT * FROM stream
        WHERE (from_address = ? OR to_address = ?) AND token_address = ? AND start_timestamp + duration <= ? AND accrued = 0 AND swap_id IS NULL
        """,
        (account_address, account_address, token_address, current_timestamp),
    )
    rows = cursor.fetchall()

    streams = []
    for row in rows:
        streams.append(stream_from_row(row))

    return streams


def get_stream_by_id(connection, stream_id) -> Stream:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT * FROM stream
        WHERE id = ?
        """,
        (stream_id,),
    )
    row = cursor.fetchone()

    if row is not None:
        return stream_from_row(row)
    else:
        return None


def get_user_shares(connection, account_address, token_address) -> int:
    create_account_if_not_exists(connection, account_address)
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT shares FROM balance
        WHERE account_address = ? AND token_address = ?
        """,
        (account_address, token_address),
    )
    row = cursor.fetchone()

    return str_to_int(row[0]) if row else 0


def set_users_shares(connection, account_address, token_address, shares) -> None:
    create_account_if_not_exists(connection, account_address)
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO balance (account_address, token_address, shares)
        VALUES (?, ?, ?)
        ON CONFLICT(account_address, token_address)
        DO UPDATE SET shares = EXCLUDED.shares
        """,
        (account_address, token_address, int_to_str(shares)),
    )


def add_stream(connection, stream) -> int:
    create_account_if_not_exists(connection, stream.from_address)
    create_account_if_not_exists(connection, stream.to_address)
    create_token_if_not_exists(connection, stream.token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO stream (from_address, to_address, start_timestamp, duration, amount, token_address, accrued, swap_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stream.from_address,
            stream.to_address,
            stream.start_timestamp,
            stream.duration,
            int_to_str(stream.amount),
            stream.token_address,
            1 if stream.accrued else 0,
            stream.swap_id,
        ),
    )

    return cursor.lastrowid


def update_stream_amount_duration(connection, stream_id, duration, amount):
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE stream
        SET duration = ?, amount = ?
        WHERE id = ?
        """,
        (duration, int_to_str(amount), stream_id),
    )


def merge_refunds(refunds):
    # Convert the list of tuples to a list of dictionaries for easier manipulation
    refunds_dict = [
        {
            "swap_id": r[0],
            "token_address": r[1],
            "amount": r[2],
            "start_timestamp": r[3],
            "duration": r[4],
        }
        for r in refunds
    ]

    # Ensure there are refunds to process
    if not refunds_dict:
        return []

    # Sort refunds by swap_id and start_timestamp
    refunds_dict.sort(key=lambda x: (x["swap_id"], x["start_timestamp"]))

    merged = []
    # Initialize the first refund to start merging
    current_refund = refunds_dict[0]

    for refund in refunds_dict[1:]:
        # Calculate current refund end time
        current_end_time = (
            current_refund["start_timestamp"] + current_refund["duration"]
        )

        if (
            refund["swap_id"] == current_refund["swap_id"]
            and refund["start_timestamp"] == current_end_time
        ):
            # Merge current refund with the next one by adding amounts and durations
            current_refund["amount"] += refund["amount"]
            current_refund["duration"] += refund["duration"]
        else:
            # Save the current refund and start a new merge candidate
            merged.append(current_refund)
            current_refund = refund

    # Append the last processed refund
    merged.append(current_refund)

    # Convert the list of dictionaries back to a list of tuples for output
    return [
        (
            r["swap_id"],
            r["token_address"],
            r["amount"],
            r["start_timestamp"],
            r["duration"],
        )
        for r in merged
    ]


def create_swap_refunds(connection, refunds):
    data_to_insert = merge_refunds(
        [
            (
                refund["swap_id"],
                refund["token_address"],
                refund["amount"],
                refund["start_timestamp"],
                refund["duration"],
            )
            for refund in refunds
        ]
    )

    cursor = connection.cursor()
    cursor.executemany(
        """
        INSERT into swap_refund (swap_id, token_address, amount, start_timestamp, duration)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                refund[0],
                refund[1],
                int_to_str(refund[2]),
                refund[3],
                refund[4],
            )
            for refund in data_to_insert
        ],
    )
    return cursor.lastrowid


def update_stream_amount_duration_batch(connection, stream_durations_amounts_ids):
    cursor = connection.cursor()
    cursor.executemany(
        """
        UPDATE stream
        SET duration = ?, amount = ?
        WHERE id = ?
        """,
        stream_durations_amounts_ids,
    )
    return cursor.lastrowid


def update_stream_accrued(connection, stream_id, accrued):
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE stream
        SET accrued = ?
        WHERE id = ?
        """,
        (1 if accrued else 0, stream_id),
    )


def delete_stream_by_id(connection, stream_id):
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM stream
        WHERE id = ?
        """,
        (stream_id,),
    )


def get_token_total_assets(connection, token_address) -> int:
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT total_assets, total_shares FROM token
        WHERE address = ?
        """,
        (token_address,),
    )
    row = cursor.fetchone()

    if row is None:
        return 0

    return str_to_int(row[0])


def set_token_total_assets(connection, token_address: str, total_assets: int):
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE token
        SET total_assets = ?
        WHERE address = ?
        """,
        (int_to_str(total_assets), token_address),
    )


def get_token_total_shares(connection, token_address) -> int:
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT total_shares FROM token
        WHERE address = ?
        """,
        (token_address,),
    )
    row = cursor.fetchone()
    return str_to_int(row[0]) if row else 0


def set_token_total_shares(connection, token_address: str, total_shares: int):
    create_token_if_not_exists(connection, token_address)
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE token
        SET total_shares = ?
        WHERE address = ?
        """,
        (int_to_str(total_shares), token_address),
    )


def set_last_timestamp_processed(
    connection, pair_address: str, last_timestamp_processed: int
):
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE pair
        SET last_timestamp_processed = ?
        WHERE address = ?
        """,
        (
            last_timestamp_processed,
            pair_address,
        ),
    )


def store_spot_prices(connection, spot_prices):
    cursor = connection.cursor()
    cursor.executemany(
        """
        INSERT INTO spot_price (pair_address, token_0_address, token_1_address, price, timestamp)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(pair_address, timestamp) DO UPDATE SET
            token_0_address = excluded.token_0_address,
            token_1_address = excluded.token_1_address,
            price = excluded.price
        """,
        [
            (
                s["pair_address"],
                s["token_0_address"],
                s["token_1_address"],
                int_to_str(s["price"]),
                s["timestamp"],
            )
            for s in spot_prices
        ],
    )


def store_swap_executions(connection, swap_executions):
    cursor = connection.cursor()
    cursor.executemany(
        """
        INSERT INTO swap_execution (swap_id, token_to_pair_address, token_from_pair_address, amount_to_pair, amount_from_pair, refund_from_pair, from_timestamp, to_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(swap_id, from_timestamp, to_timestamp) DO UPDATE SET
            token_to_pair_address = excluded.token_to_pair_address,
            token_from_pair_address = excluded.token_from_pair_address,
            amount_to_pair = excluded.amount_to_pair,
            amount_from_pair = excluded.amount_from_pair,
            refund_from_pair = excluded.refund_from_pair,
            from_timestamp = excluded.from_timestamp,
            to_timestamp = excluded.to_timestamp
        """,
        [
            (
                s["swap_id"],
                s["token_to_pair_address"],
                s["token_from_pair_address"],
                int_to_str(s["amount_to_pair"]),
                int_to_str(s["amount_from_pair"]),
                int_to_str(s["refund_from_pair"]),
                s["from_timestamp"],
                s["to_timestamp"],
            )
            for s in swap_executions
        ],
    )


# Test only
def stream_test(payload, sender, start_timestamp, connection):
    split_number = int(payload["args"]["split_number"])
    split_amount = int(payload["args"]["amount"]) // split_number

    sender_checksum = to_checksum_address(sender)
    receiver_checksum = to_checksum_address(payload["args"]["receiver"])
    token_checksum = to_checksum_address(payload["args"]["token"])

    create_account_if_not_exists(connection, sender_checksum)
    create_account_if_not_exists(connection, receiver_checksum)
    create_token_if_not_exists(connection, token_checksum)
    stream_data = []
    amt = str(int(split_amount))
    duration = int(payload["args"]["duration"])
    for number in range(split_number):
        stream_data.append(
            (
                sender_checksum,
                receiver_checksum,
                start_timestamp,
                duration + number,
                amt,
                token_checksum,
                0,
                None,
            )
        )

    cursor = connection.cursor()
    cursor.executemany(
        """
                INSERT INTO stream (from_address, to_address, start_timestamp, duration, amount, token_address, accrued, swap_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
        stream_data,
    )


@dataclass
class PairInfo:
    pair_address: str
    token_0_address: str
    token_1_address: str
    last_timestamp_processed: int


def get_updatable_pairs(connection, wallet_address, token_address, start_timestamp):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT DISTINCT s.pair_address, p.token_0_address, p.token_1_address, p.last_timestamp_processed
        FROM swap s
        JOIN stream st ON s.id = st.swap_id
        JOIN pair p ON s.pair_address = p.address
        WHERE st.to_address = ? AND st.accrued = 0 
        AND (p.token_0_address = ? OR p.token_1_address = ?)
        AND st.start_timestamp <= ?
        """,
        (
            wallet_address,
            token_address,
            token_address,
            start_timestamp,
        ),
    )
    result = cursor.fetchall()
    return [PairInfo(*row) for row in result]


def get_wallet_token_streamed(connection, wallet_address):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT DISTINCT token_address
        FROM stream
        WHERE from_address = ? OR to_address = ?
        """,
        (
            wallet_address,
            wallet_address,
        ),
    )
    return cursor.fetchall()


@dataclass
class Swap:
    id: int
    from_pair_id: str
    from_pair_to_address: str
    from_pair_amount: str
    from_pair_duration: int
    to_pair_amount: str
    to_pair_start_timestamp: int
    to_pair_duration: int
    to_pair_token_address: str
    condition_type: str = None
    condition_value: int = None
    rate: int = 0  # default rate initialization


def get_swaps_for_pair_address(connection, pair_address: str, to_timestamp: int):

    cursor = connection.cursor()

    # Execute the SQL query
    cursor.execute(
        """
        SELECT 
            st_from_pair.id AS from_pair_id,
            st_from_pair.amount AS from_pair_amount,
            st_from_pair.duration AS from_pair_duration,
            st_to_pair.amount AS to_pair_amount, 
            st_to_pair.start_timestamp AS to_pair_start_timestamp,
            st_to_pair.duration AS to_pair_duration,
            st_to_pair.token_address AS to_pair_token_address,
            s.condition_type,
            s.condition_value,
            st_from_pair.to_address,
            s.id
        FROM 
            swap s
        JOIN 
            stream st_to_pair ON s.id = st_to_pair.swap_id
        JOIN 
            stream st_from_pair ON s.id = st_from_pair.swap_id
        WHERE 
            s.pair_address = ?
        AND 
            st_to_pair.start_timestamp <= ?
        AND 
            st_from_pair.duration != st_to_pair.duration
        AND 
            st_to_pair.to_address = ? AND st_from_pair.from_address = ?
        AND 
            st_to_pair.duration > 0
        """,
        (
            pair_address,
            to_timestamp,
            pair_address,
            pair_address,
        ),
    )

    result = cursor.fetchall()
    return [
        Swap(
            id=row[10],
            from_pair_id=row[0],
            from_pair_amount=row[1],
            from_pair_duration=row[2],
            to_pair_amount=row[3],
            to_pair_start_timestamp=row[4],
            to_pair_duration=row[5],
            to_pair_token_address=row[6],
            condition_type=row[7],
            condition_value=str_to_int(row[8]),
            from_pair_to_address=row[9],
            rate=0,  # Initial default rate, can be adjusted later as needed
        )
        for row in result
    ]
