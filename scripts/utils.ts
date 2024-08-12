import { ERC20Portal__factory, InputBox__factory, CartesiDApp__factory } from "@cartesi/rollups";
import { Contract, Wallet, ethers } from "ethers";
import { ERC20Mock__factory, InputBoxWrapper__factory } from "./contract-types";

export const privateKey =
  "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"; // hardhat node's first account private key

export const privateKeyRandomUser = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d";

const erc20PortalAddress = "0x9C21AEb2093C32DDbC53eEF24B873BDCd1aDa1DB";
const inputBoxAddress = "0x59b22D57D4f067708AB0c00552767405926dc768";
const dappAddress = "0xab7528bb862fb57e8a2bcd567a2e929a0be56a5e";


export const wait = (s: number) => new Promise((resolve) => setTimeout(resolve, s * 1000));

const hexlify = (text: string) =>
  ethers.hexlify(ethers.toUtf8Bytes(text)) as `0x${string}`;

export const getUnrawpBody = (token: string, amount: bigint): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "unwrap",
      args: { token, amount: amount.toString() },
    })
  );

export const getSwapBody = (
  amountIn: bigint,
  amountOutMin: bigint,
  path: [string, string],
  duration: number,
  start: number,
  to: string
): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "swap",
      args: {
        amount_in: amountIn.toString(),
        amount_out_min: amountOutMin.toString(),
        path,
        duration,
        start,
        to,
      },
    })
  );

export const getStreamBody = (
  token: string,
  receiver: string,
  amount: bigint,
  duration: number,
  start: number
): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "stream",
      args: {
        token,
        receiver: receiver,
        amount: amount.toString(),
        duration,
        start,
      },
    })
  );

export const getStreamTestBody = (
  token: string,
  receiver: string,
  amount: bigint,
  duration: number,
  start: number,
  split_number: number
): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "stream_test",
      args: {
        token,
        receiver: receiver,
        amount: amount.toString(),
        duration,
        start,
        split_number,
      },
    })
  );

export const getAddLiquidityBody = (
  token_a: string,
  token_b: string,
  token_a_desired: bigint,
  token_b_desired: bigint,
  token_a_min: bigint,
  token_b_min: bigint,
  to: string
): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "add_liquidity",
      args: {
        token_a,
        token_b,
        token_a_desired: token_a_desired.toString(),
        token_b_desired: token_b_desired.toString(),
        token_a_min: token_a_min.toString(),
        token_b_min: token_b_min.toString(),
        to,
      },
    })
  );

export const getRemoveLiquidityBody = (
  token_a: string,
  token_b: string,
  liquidity: bigint,
  amount_a_min: bigint,
  amount_b_min: bigint,
  to: string
): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "remove_liquidity",
      args: {
        token_a,
        token_b,
        liquidity: liquidity.toString(),
        amount_a_min: amount_a_min.toString(),
        amount_b_min: amount_b_min.toString(),
        to,
      },
    })
  );

export const getClaimAdminBody = (walletAddress: string): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "claim_admin",
      args: {
        admin: walletAddress,
      },
    })
  );

export const getSetInputBoxWrapperBody = (inputBoxWrapperAddress: string): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "set_input_box_wrapper",
      args: {
        input_box_wrapper: inputBoxWrapperAddress,
      },
    })
  );

export const getSetYieldBridgeBody = (yieldBridgeAddress: string): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "set_yield_bridge",
      args: {
        yield_bridge: yieldBridgeAddress,
      },
    })
  );

export const getCancelBody = (
  token: string,
  parent_id?: string,
  stream_id?: string
): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "cancel_stream",
      args: {
        token,
        parent_id,
        stream_id,
      },
    })
  );

export const getWithdrawBody = (token: string, amount: bigint, recipient: string): `0x${string}` =>
  hexlify(
    JSON.stringify({
      method: "withdraw",
      args: {
        token,
        amount: amount.toString(),
        recipient,
      },
    })
  );

export const approveErc20 = async (
  tokenAddress: string,
  amount: string,
  spender: string,
  wallet: Wallet
): Promise<void> => {
  const contract = ERC20Mock__factory.connect(tokenAddress, wallet);

  const tx = await contract.approve(spender, amount);
  await tx.wait();
  console.log("Approved", amount, "tokens to", spender);
};

export const inputBoxAddInput = async (payload: string, wallet: Wallet): Promise<void> => {

  const contract = new ethers.Contract(inputBoxAddress, InputBox__factory.abi, wallet);

  const tx = await contract.addInput(dappAddress, payload);
  await tx.wait();
  console.log("Input added to", inputBoxAddress);
};

export const inputBoxWrapperAddInput = async (payload: string, inputBoxWrapperAddress: string, wallet: Wallet): Promise<void> => {

  const contract = InputBoxWrapper__factory.connect(inputBoxWrapperAddress, wallet);

  const tx = await contract.addInput(dappAddress, payload);
  await tx.wait();
  console.log("Input added to", inputBoxWrapperAddress);
};

export const stream = async (
  token: string,
  receiver: string,
  amount: bigint,
  duration: number,
  start: number,
  wallet: Wallet
): Promise<void> => {
  return inputBoxAddInput(
    getStreamBody(token, receiver, amount, duration, start), wallet
  );
};

export const addLiquidity = async (
  token_a: string,
  token_b: string,
  token_a_desired: bigint,
  token_b_desired: bigint,
  token_a_min: bigint,
  token_b_min: bigint,
  to: string,
  wallet: Wallet
): Promise<void> => {
  return inputBoxAddInput(
    getAddLiquidityBody(
      token_a,
      token_b,
      token_a_desired,
      token_b_desired,
      token_a_min,
      token_b_min,
      to
    ), wallet
  );
}

export const swap = async (
  amountIn: bigint,
  amountOutMin: bigint,
  path: [string, string],
  duration: number,
  start: number,
  to: string,
  wallet: Wallet
): Promise<void> => {
  return inputBoxAddInput(
    getSwapBody(amountIn, amountOutMin, path, duration, start, to), wallet
  );
}

export const claimAdmin = async (walletAddress: string, inputBoxWrapperAddress: string, wallet: Wallet): Promise<void> => {
  return inputBoxWrapperAddInput(
    getClaimAdminBody(walletAddress), inputBoxWrapperAddress, wallet
  );
}

export const setInputBoxWrapper = async (inputBoxWrapperAddress: string, wallet: Wallet): Promise<void> => {
  return inputBoxWrapperAddInput(
    getSetInputBoxWrapperBody(inputBoxWrapperAddress), inputBoxWrapperAddress, wallet
  );
}

export const setYieldBridge = async (yieldBridgeAddress: string, inputBoxWrapperAddress: string, wallet: Wallet): Promise<void> => {
  return inputBoxWrapperAddInput(
    getSetYieldBridgeBody(yieldBridgeAddress), inputBoxWrapperAddress, wallet
  );
}

export const withdraw = async (token: string, amount: bigint, recipient: string, wallet: Wallet, inputBoxWrapperAddress: string): Promise<void> => {
  return inputBoxWrapperAddInput(
    getWithdrawBody(token, amount, recipient), inputBoxWrapperAddress, wallet
  );
}



async function sendGraphQLQuery(endpoint: string, query: string, variables?: Record<string, any>) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      variables,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  return data;
}

interface VouchersResponse {
  data: {
    vouchers: {
      edges: Array<{
        node: {
          input: {
            msgSender: string;
            payload: string;
            index: number;
          };
          payload: string;
          proof: {
            validity: {
              inputIndexWithinEpoch: number;
              outputIndexWithinInput: number;
              outputHashesRootHash: string;
              vouchersEpochRootHash: string;
              noticesEpochRootHash: string;
              machineStateHash: string;
              outputHashInOutputHashesSiblings: string[];
              outputHashesInEpochSiblings: string[];
            };
            context: string;
          };
          destination: string;
        }
      }>;
    }
  }
}

export async function getVouchers(): Promise<VouchersResponse> {
  const query = `
      query GetVouchers {
        vouchers {
          edges {
            node {
              input {
                msgSender
                payload
                index
              }
              payload
              proof {
                validity {
                  inputIndexWithinEpoch
                  outputIndexWithinInput
                  outputHashesRootHash
                  vouchersEpochRootHash
                  noticesEpochRootHash
                  machineStateHash
                  outputHashInOutputHashesSiblings
                  outputHashesInEpochSiblings
                }
                context
              }
              destination
            }
          }
        }
      }
  `;
  const data = await sendGraphQLQuery("http://localhost:8080/graphql", query);
  if ((data as VouchersResponse).data.vouchers.edges.length === 0) {
    await wait(3);
    return getVouchers();
  }
  return data;
}

export async function executeVoucher(voucher: VouchersResponse, wallet: Wallet): Promise<void> {
  const provider = new ethers.JsonRpcProvider("http://localhost:8545");
  const contract = CartesiDApp__factory.connect(dappAddress, provider);
  // encode function call
  const functionCall = contract.interface.encodeFunctionData("executeVoucher", [voucher.data.vouchers.edges[0].node.destination, voucher.data.vouchers.edges[0].node.payload, voucher.data.vouchers.edges[0].node.proof]);

  const tx = await provider.send("eth_sendTransaction", [{
    from: wallet.address,
    to: dappAddress,
    data: functionCall,
  }]);
}

export async function inspectBalance(walletAddress: string, tokenAddress: string, timestamp: number): Promise<string> {
  const response = await fetch("http://localhost:8080/inspect", {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      data: "balance",
      token_address: tokenAddress,
      wallet_address: walletAddress,
      timestamp: timestamp
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  const result = JSON.parse(ethers.toUtf8String(data.reports[0].payload));
  return result.message;
}


export async function increaseTime(provider: ethers.JsonRpcProvider, seconds: number) {
  await provider.send("evm_increaseTime", [seconds]);
  await provider.send("evm_mine", []);
}