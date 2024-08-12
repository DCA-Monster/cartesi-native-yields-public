import os
from dapp.db import Swap
from typing import List, Dict, Set, Tuple

from dapp.util import (
    with_checksum_address,
)


@with_checksum_address
def hook(connection, token_address, wallet, to_timestamp):
    return True
