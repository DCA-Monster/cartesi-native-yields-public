from dapp.streamrebasetoken import StreamRebaseToken
from dapp.db import (
    get_admin,
    get_connection,
    get_yield_bridge,
    set_admin,
    set_input_box_wrapper,
    set_yield_bridge,
    get_input_box_wrapper,
)
from dapp.logger import logger
from dapp.util import (
    ZERO_ADDRESS,
    hex_to_str,
    logger,
    rollup_server,
    str_to_hex,
)

from eth_abi import decode, encode
from eth_utils import is_same_address
import json
import requests


def send_post_request(endpoint, payload):
    url = rollup_server + endpoint
    json_payload = {"payload": str_to_hex(json.dumps(payload))}

    response = requests.post(url, json=json_payload)

    if response.status_code not in (200, 202):
        logger.error(
            f"Failed POST request to {url}. Status: {response.status_code}. Response: {response.text}"
        )
    else:
        logger.info(
            f"Successful POST request to {url}. Status: {response.status_code}. Response: {response.text}"
        )

    return response


def report_error(msg, payload):
    error_log = {
        "error": True,
        "message": msg,
        "payload": payload,
    }
    logger.error(error_log)
    send_post_request("/report", error_log)
    return "reject"


def report_success(msg, payload):
    success_log = {
        "error": False,
        "message": msg,
        "payload": payload,
    }
    """Function to report successful operations."""
    logger.info(f"Reporting success {success_log}")
    send_post_request("/report", success_log)
    return "accept"


def only_admin(sender, connection):
    admin_address = get_admin(connection)
    if not is_same_address(sender, admin_address):
        raise Exception(f"Not from admin")
    return True


def only_input_box_wrapper(sender, connection):
    input_box_wrapper_address = get_input_box_wrapper(connection)
    if not is_same_address(sender, input_box_wrapper_address):
        raise Exception(f"Not from input box wrapper")
    return True


def is_yield_bridge(sender, connection):
    yield_bridge_address = get_yield_bridge(connection)
    return is_same_address(sender, yield_bridge_address)


def is_input_box_wrapper(sender, connection):
    input_box_wrapper_address = get_input_box_wrapper(connection)
    return is_same_address(sender, input_box_wrapper_address)


def handle_action(data, connection):

    binary = bytes.fromhex(data["payload"][2:])
    decoded = decode(["address", "address[]", "uint256[]", "bytes"], binary)
    logger.info(f"Received advance request data {decoded}")

    parent_sender = data["metadata"]["msg_sender"]
    sender = decoded[0]
    tokens_to_rebase = decoded[1]
    amounts_to_rebase = decoded[2]
    encoded_action = decoded[3]

    timestamp = data["metadata"]["timestamp"]

    admin_address = get_admin(connection)
    is_input_box = is_input_box_wrapper(parent_sender, connection)
    is_yb = is_yield_bridge(decoded[0], connection)

    if is_yb:
        only_input_box_wrapper(parent_sender, connection)
        decoded_deposit = decode(
            ["address", "address", "uint256", "address", "bytes"], decoded[3]
        )
        assets_amount = decoded_deposit[2]
        recipient = decoded_deposit[3]
        StreamRebaseToken(connection, decoded_deposit[0]).mint_assets(
            assets_amount=assets_amount,
            wallet=recipient,
        )
        encoded_action = decoded_deposit[4]

    if is_input_box:
        for i in range(len(tokens_to_rebase)):
            StreamRebaseToken(connection, tokens_to_rebase[i]).rebase(
                amounts_to_rebase[i]
            )

    if not encoded_action:
        return "accept"

    str_payload = encoded_action
    payload = json.loads(str_payload)

    if payload["method"] == "claim_admin" and is_same_address(
        admin_address, ZERO_ADDRESS
    ):
        set_admin(connection, payload["args"]["admin"])
        return "accept"

    if payload["method"] == "set_admin" and only_admin(decoded[0], connection):
        set_admin(connection, payload["args"]["admin"])
        return "accept"

    if payload["method"] == "set_input_box_wrapper" and only_admin(
        decoded[0], connection
    ):
        set_input_box_wrapper(connection, payload["args"]["input_box_wrapper"])
        return "accept"

    if payload["method"] == "set_yield_bridge" and only_admin(decoded[0], connection):
        set_yield_bridge(connection, payload["args"]["yield_bridge"])
        return "accept"

    # From here on, only the input box wrapper can call these functions
    only_input_box_wrapper(parent_sender, connection)

    if payload["method"] == "stream":
        StreamRebaseToken(connection, payload["args"]["token"]).transfer(
            receiver=payload["args"]["receiver"],
            amount=int(payload["args"]["amount"]),
            duration=int(payload["args"]["duration"]),
            start_timestamp=int(payload["args"]["start"]),
            sender=sender,
            current_timestamp=timestamp,
        )
    elif payload["method"] == "withdraw":
        token_address = payload["args"]["token"]
        token = StreamRebaseToken(connection, token_address)
        amount = int(payload["args"]["amount"])
        recipient = payload["args"]["recipient"]
        token.burn_assets(
            assets_amount=amount,
            sender=sender,
            current_timestamp=timestamp,
        )

        WITHDRAW_FUNCTION_SELECTOR = b"\x1fQ\x95\xb7"
        withdraw_payload = WITHDRAW_FUNCTION_SELECTOR + encode(
            ["address", "uint256", "address"],
            [token_address, amount, recipient],
        )
        voucher = {
            "destination": get_yield_bridge(connection),
            "payload": "0x" + withdraw_payload.hex(),
        }
        logger.info(f"Issuing voucher {voucher}")
        response = requests.post(rollup_server + "/voucher", json=voucher)
        logger.info(
            f"Received voucher status {response.status_code} body {response.content}"
        )
    elif payload["method"] == "cancel_stream":
        token = StreamRebaseToken(connection, payload["args"]["token"]).cancel_stream(
            stream_id=int(payload["args"]["stream_id"]),
            sender=sender,
            current_timestamp=timestamp,
        )
    else:
        raise Exception(f"Unknown method {payload['method']}")

    return "accept"


def handle_advance(data):
    logger.info(f"Received advance request data {data}")
    connection = get_connection()
    status = "accept"
    try:
        status = handle_action(data, connection)
        report_success("Success", str_to_hex(json.dumps(data)))
        connection.commit()
        connection.close()
    except Exception as e:
        connection.rollback()
        status = "reject"
        report_error(str(e), data["payload"])

    return status


def handle_inspect(data):
    logger.info(f"Received inspect request data {data}")

    response = "accept"
    try:
        payload = hex_to_str(data["payload"])
        json_payload = json.loads(payload)
        connection = get_connection()

        if json_payload["data"] == "balance":
            token_address = json_payload["token_address"]
            wallet_address = json_payload["wallet_address"]
            balance = StreamRebaseToken(connection, token_address).balance_of(
                account_address=wallet_address,
                at_timestamp=json_payload["timestamp"],
            )
            return report_success(str(balance), data["payload"])

        return report_success("ok", data["payload"])
    except Exception as e:
        response = report_error(str(e), data["payload"])
    return response


def handle(rollup_request):
    handlers = {
        "advance_state": handle_advance,
        "inspect_state": handle_inspect,
    }
    handler = handlers[rollup_request["request_type"]]
    return handler(rollup_request["data"])
