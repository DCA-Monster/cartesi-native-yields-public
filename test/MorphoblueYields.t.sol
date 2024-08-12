// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BaseTest} from "../lib/morpho-blue/test/forge/BaseTest.sol";
import {YieldBridge} from "../src/YieldBridge.sol";
import {InputBoxWrapper} from "../src/InputBoxWrapper.sol";
import {IInputBox} from "@cartesi-rollup-contracts/inputs/IInputBox.sol";
import {InputBox} from "@cartesi-rollup-contracts/inputs/InputBox.sol";
import {AssetAllocator} from "../src/AssetAllocator.sol";
import {MarketParamsLib} from "@morpho-blue/libraries/MarketParamsLib.sol";
import {MorphoLib} from "@morpho-blue/libraries/periphery/MorphoLib.sol";
import {Id, IMorphoStaticTyping, MarketParams, IMorpho} from "@morpho-blue/interfaces/IMorpho.sol";

contract MorphoblueYieldsTest is BaseTest {
    IInputBox public inputBox;
    InputBoxWrapper public inputBoxWrapper;
    YieldBridge public yieldBridge;
    AssetAllocator public assetAllocator;
    address public USER;

    using MorphoLib for IMorpho;

    function setUp() public override {
        super.setUp();
        inputBox = new InputBox();
        inputBoxWrapper = new InputBoxWrapper(address(inputBox));
        yieldBridge = new YieldBridge(address(inputBoxWrapper), address(this));
        inputBoxWrapper.setYieldBridge(address(yieldBridge));
        assetAllocator = new AssetAllocator(
            address(morpho), bytes32(abi.encodePacked(MarketParamsLib.id(marketParams))), address(yieldBridge)
        );
        yieldBridge.setAssetAllocator(address(loanToken), address(assetAllocator));

        USER = makeAddr("User");
    }

    function test_lp_yields_morpho() public {
        uint256 amountToDeposit = 10 ether;
        uint256 amountBorrowed = 5 ether;
        loanToken.setBalance(USER, amountToDeposit);

        assertEq(assetAllocator.getBalance(), 0, "AssetAllocator balance is not equal to 0");

        vm.startPrank(USER);
        loanToken.approve(address(yieldBridge), amountToDeposit);
        yieldBridge.depositERC20Tokens(address(loanToken), USER, amountToDeposit, "");
        vm.stopPrank();

        vm.startPrank(BORROWER);
        collateralToken.setBalance(BORROWER, HIGH_COLLATERAL_AMOUNT);
        collateralToken.approve(address(morpho), type(uint256).max);
        morpho.supplyCollateral(marketParams, HIGH_COLLATERAL_AMOUNT, BORROWER, hex"");
        morpho.borrow(marketParams, amountBorrowed, 0, BORROWER, BORROWER);
        vm.stopPrank();

        loanToken.setBalance(BORROWER, 200 ether);
        uint256 balance = assetAllocator.getBalance();

        vm.warp(block.timestamp + 365 days);

        vm.startPrank(BORROWER);

        Id id = MarketParamsLib.id(marketParams);
        uint256 shares = morpho.borrowShares(id, BORROWER);
        morpho.repay(marketParams, 0, shares, BORROWER, hex"");
        vm.stopPrank();

        morpho.accrueInterest(marketParams);

        assertTrue(assetAllocator.getBalance() > balance);

        // test add input
        string memory action = '{"method":"test","args":{"test":true}}';
        inputBoxWrapper.addInput(address(yieldBridge), bytes(action));

        // withdraw assets
        uint256 userBalance = loanToken.balanceOf(USER);
        uint256 availableBalance = assetAllocator.getBalance();
        yieldBridge.withdrawERC20Tokens(address(loanToken), availableBalance, USER);
        assertEq(loanToken.balanceOf(USER), userBalance + availableBalance);
    }
}
