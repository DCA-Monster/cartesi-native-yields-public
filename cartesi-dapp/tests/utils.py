from dapp.streamrebasetoken import StreamRebaseToken
from dapp.util import with_checksum_address


def get_unique_addresses_for_token(connection, token_address):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT DISTINCT from_address FROM stream WHERE token_address = ?
        UNION
        SELECT DISTINCT to_address FROM stream WHERE token_address = ?
        """,
        (token_address, token_address),
    )
    stream_addresses = set(cursor.fetchall())

    cursor.execute(
        """
        SELECT DISTINCT account_address FROM balance WHERE token_address = ?
        """,
        (token_address,),
    )
    balance_addresses = set(cursor.fetchall())

    unique_addresses = {
        address for tup in (stream_addresses | balance_addresses) for address in tup
    }

    return list(unique_addresses)


def get_pair(connection, pair_address):
    cursor = connection.cursor()
    cursor.execute(
        """
            SELECT address, token_0_address, token_1_address, last_timestamp_processed
            FROM pair
            WHERE address = ?
            """,
        (pair_address,),
    )
    row = cursor.fetchone()
    if row:
        return {
            "address": row[0],
            "token_0_address": row[1],
            "token_1_address": row[2],
            "last_timestamp_processed": row[3],
        }
    return None


@with_checksum_address
def calculate_total_supply_token(connection, token_address):
    addresses = get_unique_addresses_for_token(connection, token_address)
    token = StreamRebaseToken(connection, token_address)
    total_supply = 0
    for wallet in [address for address in addresses]:
        balance = token.balance_of(wallet, 2**63 - 1)
        assert balance >= 0, "Balance cannot be negative."
        total_supply += balance
    return total_supply
