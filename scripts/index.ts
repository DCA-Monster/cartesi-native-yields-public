import { BytesLike, ethers, parseEther, ZeroAddress } from "ethers";
import { AssetAllocator__factory, EventsLib__factory, InputBoxWrapper__factory, Morpho__factory, YieldBridge__factory } from "./contract-types";
import { ERC20Mock__factory } from "./contract-types";
import { IrmMock__factory } from "./contract-types";
import { OracleMock__factory } from "./contract-types";
import { claimAdmin, executeVoucher, getVouchers, increaseTime, inspectBalance, setInputBoxWrapper, setYieldBridge, wait, withdraw } from "./utils";

export const privateKey =
    "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"; // anvil node's first account private key

export const secondPrivateKey = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"; // anvil node's second account private key

const inputBoxAddress = "0x59b22D57D4f067708AB0c00552767405926dc768";
const dappAddress = "0xab7528bb862fb57e8a2bcd567a2e929a0be56a5e";

const main = async () => {
    const provider = new ethers.JsonRpcProvider("http://localhost:8545");
    const wallet = new ethers.Wallet(privateKey, provider);
    const secondWallet = new ethers.Wallet(secondPrivateKey, provider);

    console.log("Deploying InputBoxWrapper...");
    const inputBoxWrapper = await (await (new InputBoxWrapper__factory(wallet)).deploy(inputBoxAddress)).waitForDeployment();
    console.log("InputBoxWrapper deployed at:", await inputBoxWrapper.getAddress());

    console.log("Deploying YieldBridge...");
    const yieldBridge = await (await (new YieldBridge__factory(wallet)).deploy(inputBoxWrapper.getAddress(), dappAddress)).waitForDeployment();
    console.log("YieldBridge deployed at:", await yieldBridge.getAddress());

    console.log("Setting YieldBridge on InputBoxWrapper...");
    await (await inputBoxWrapper.setYieldBridge(yieldBridge.getAddress())).wait();
    console.log("YieldBridge set on InputBoxWrapper");

    console.log("Deploying test tokens...");
    const loanToken = await (await (new ERC20Mock__factory(wallet)).deploy()).waitForDeployment();
    const collateralToken = await (await (new ERC20Mock__factory(wallet)).deploy()).waitForDeployment();
    console.log("LoanToken deployed at:", await loanToken.getAddress());
    console.log("CollateralToken deployed at:", await collateralToken.getAddress());

    console.log("Deploying and configuring Morpho...");
    const morpho = await (await (new Morpho__factory(wallet)).deploy(wallet.address)).waitForDeployment();
    console.log("Morpho deployed at:", await morpho.getAddress());

    const irmMock = await (await (new IrmMock__factory(wallet)).deploy()).waitForDeployment();
    const oracleMock = await (await (new OracleMock__factory(wallet)).deploy()).waitForDeployment();
    console.log("IrmMock deployed at:", await irmMock.getAddress());
    console.log("OracleMock deployed at:", await oracleMock.getAddress());

    console.log("Setting OracleMock price...");
    await (await oracleMock.setPrice(parseEther("1") * parseEther("1"))).wait();

    const defaultLltv = parseEther("0.8");
    console.log("Enabling IRM and LLTV on Morpho...");
    await (await morpho.enableIrm(ZeroAddress)).wait();
    await (await morpho.enableIrm(irmMock.getAddress())).wait();
    await (await morpho.enableLltv(defaultLltv)).wait();
    await (await morpho.setFeeRecipient(wallet.address)).wait();

    const marketParams = {
        loanToken: loanToken.getAddress(),
        collateralToken: collateralToken.getAddress(),
        irm: irmMock.getAddress(),
        oracle: oracleMock.getAddress(),
        lltv: defaultLltv,
    };

    console.log("Creating market on Morpho...");
    await (await morpho.createMarket(marketParams)).wait();

    console.log("Finding market ID...");
    const eventsLib = EventsLib__factory.connect(await morpho.getAddress(), provider);
    const marketCreatedEvent = (await (await eventsLib.queryFilter(eventsLib.filters.CreateMarket()))).pop();
    const marketId = marketCreatedEvent?.args[0] || 0;
    console.log("Market ID:", marketId);

    console.log("Deploying AssetAllocator...");
    const assetAllocator = await (await (new AssetAllocator__factory(wallet)).deploy(morpho.getAddress(), marketId as BytesLike, await yieldBridge.getAddress())).waitForDeployment();
    console.log("AssetAllocator deployed at:", await assetAllocator.getAddress());

    console.log("Setting AssetAllocator on YieldBridge...");
    await (await yieldBridge.setAssetAllocator(await loanToken.getAddress(), await assetAllocator.getAddress())).wait();

    console.log("Claiming admin on InputBoxWrapper...");
    await claimAdmin(wallet.address, await inputBoxWrapper.getAddress(), wallet);
    await setInputBoxWrapper(await inputBoxWrapper.getAddress(), wallet);
    await setYieldBridge(await yieldBridge.getAddress(), await inputBoxWrapper.getAddress(), wallet);

    console.log("YieldBridge: ", await yieldBridge.getAddress());
    console.log("InputBoxWrapper: ", await inputBoxWrapper.getAddress());
    console.log("AssetAllocator: ", await assetAllocator.getAddress());

    const depositAmount = ethers.parseEther("200");
    console.log("Setting balance and approving loanToken...");
    await (await loanToken.setBalance(wallet.address, depositAmount)).wait();
    await (await loanToken.approve(await yieldBridge.getAddress(), depositAmount)).wait();

    console.log("Depositing ERC20 tokens into YieldBridge...");
    await (await yieldBridge.depositERC20Tokens(await loanToken.getAddress(), dappAddress, depositAmount, "0x")).wait();
    await wait(3);

    console.log("Inspecting Dapp balance after deposit...");
    let time = await provider.getBlock("latest");
    let balance = await inspectBalance(wallet.address, await loanToken.getAddress(), time?.timestamp || Date.now() / 1000);
    console.log("Dapp balance after deposit: ", ethers.formatEther(balance), "WETH");

    console.log("Simulating Morpho activity and APY...");
    const highCollateralAmount = parseEther("1") * BigInt(10) ** BigInt(17);
    await (await collateralToken.setBalance(secondWallet.address, highCollateralAmount)).wait();
    await (await collateralToken.connect(secondWallet).approve(await morpho.getAddress(), highCollateralAmount)).wait();
    await (await morpho.connect(secondWallet).supplyCollateral(marketParams, highCollateralAmount, secondWallet.address, "0x")).wait();
    await (await morpho.connect(secondWallet).borrow(marketParams, ethers.parseEther("100"), 0, secondWallet.address, secondWallet.address)).wait();

    console.log("Increasing time...");
    await increaseTime(provider, 365 * 24 * 60 * 60);

    console.log("Repaying Morpho loan...");
    await (await loanToken.connect(secondWallet).approve(await morpho.getAddress(), ethers.MaxUint256)).wait();
    await (await loanToken.setBalance(secondWallet.address, ethers.parseEther("100000"))).wait();
    const position = await morpho.position(marketId as BytesLike, secondWallet.address);
    await (await morpho.connect(secondWallet).repay(marketParams, "0", position.borrowShares, secondWallet.address, "0x")).wait();

    console.log("Triggering token rebase...");
    await (await loanToken.setBalance(secondWallet.address, depositAmount)).wait();
    await (await loanToken.connect(secondWallet).approve(await yieldBridge.getAddress(), depositAmount)).wait();
    await (await yieldBridge.connect(secondWallet).depositERC20Tokens(await loanToken.getAddress(), dappAddress, depositAmount, "0x")).wait();
    await wait(3);

    console.log("Inspecting Dapp balance after Morpho Blue rebase...");
    time = await provider.getBlock("latest");
    const newBalance = await inspectBalance(wallet.address, await loanToken.getAddress(), time?.timestamp || Date.now() / 1000);
    console.log("Dapp balance after deposit: ", ethers.formatEther(newBalance), "WETH");

    console.log("Withdrawing from InputBoxWrapper...");
    await withdraw(await loanToken.getAddress(), BigInt(newBalance), wallet.address, wallet, await inputBoxWrapper.getAddress());
    await wait(3);

    console.log("Getting and executing vouchers...");
    const vouchers = await getVouchers();
    await executeVoucher(vouchers, wallet);
    await wait(3);

    console.log("Balance after voucher execution:", ethers.formatEther(newBalance), "WETH");
};

main();