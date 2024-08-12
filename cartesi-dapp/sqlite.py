import os

from dapp.db import get_connection


def initialise_db():
    try:
        db_file_path = os.getenv("DB_FILE_PATH", "dapp.sqlite")
        os.remove(db_file_path)
    except FileNotFoundError:
        pass

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dapp_addresses (
            name TEXT PRIMARY KEY,
            address TEXT NOT NULL
        )
        """
    )

    # Initialize dapp_addresses with default values
    cursor.executemany(
        "INSERT OR REPLACE INTO dapp_addresses (name, address) VALUES (?, ?)",
        [
            ("admin", "0x0000000000000000000000000000000000000000"),
            ("input_box_wrapper", "0x0000000000000000000000000000000000000000"),
            ("yield_bridge", "0x0000000000000000000000000000000000000000"),
        ],
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS account (
            address TEXT PRIMARY KEY
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS token (
            address TEXT PRIMARY KEY,
            total_assets TEXT NOT NULL,
            total_shares TEXT NOT NULL,
            FOREIGN KEY (address) REFERENCES account(address)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS balance (
            shares TEXT NOT NULL,
            account_address TEXT NOT NULL,
            token_address TEXT NOT NULL,
            FOREIGN KEY (account_address) REFERENCES account(address),
            FOREIGN KEY (token_address) REFERENCES token(address),
            PRIMARY KEY (account_address, token_address)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stream (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_address TEXT NOT NULL,
            to_address TEXT NOT NULL,
            start_timestamp INTEGER NOT NULL,
            duration INTEGER NOT NULL,
            amount TEXT NOT NULL,
            token_address TEXT NOT NULL,
            accrued INTEGER NOT NULL,
            swap_id TEXT,
            FOREIGN KEY (token_address) REFERENCES token(address),
            FOREIGN KEY (from_address) REFERENCES account(address),
            FOREIGN KEY (to_address) REFERENCES account(address)
        )
        """
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stream_from_address ON stream(from_address)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stream_to_address ON stream(to_address)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stream_token_address ON stream(token_address)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stream_accrued ON stream(accrued)")

    conn.commit()

    conn.close()


if __name__ == "__main__":
    initialise_db()
