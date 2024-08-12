// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {IAssetAllocator} from "./interfaces/IAssetAllocator.sol";
import {Id, IMorphoStaticTyping, MarketParams, IMorpho} from "@morpho-blue/interfaces/IMorpho.sol";
import {MorphoBalancesLib} from "@morpho-blue/libraries/periphery/MorphoBalancesLib.sol";
import {IERC20} from "lib/forge-std/src/interfaces/IERC20.sol";
import {SharesMathLib} from "@morpho-blue/libraries/SharesMathLib.sol";

contract AssetAllocator is IAssetAllocator {
    IMorphoStaticTyping public morpho;
    IERC20 public asset;
    MarketParams public marketParams;
    Id public marketId;
    address public yieldBridge;

    using MorphoBalancesLib for IMorpho;

    using SharesMathLib for uint256;

    constructor(address _morpho, bytes32 _marketId, address _yieldBridge) {
        marketId = Id.wrap(_marketId);
        morpho = IMorphoStaticTyping(_morpho);
        (marketParams.loanToken, marketParams.collateralToken, marketParams.oracle, marketParams.irm, marketParams.lltv)
        = morpho.idToMarketParams(marketId);
        asset = IERC20(marketParams.loanToken);
        asset.approve(address(morpho), type(uint256).max);
        yieldBridge = _yieldBridge;
    }

    function allocateAssets(uint256 amount) public {
        asset.transferFrom(msg.sender, address(this), amount);
        morpho.supply(marketParams, amount, 0, address(this), "");
    }

    function withdrawAssets(uint256 amount, address receiver) public {
        require(msg.sender == yieldBridge, "Only yieldBridge can withdraw assets");
        morpho.withdraw(marketParams, amount, 0, address(this), receiver);
    }

    function getBalance() public view returns (uint256) {
        return IMorpho(address(morpho)).expectedSupplyAssets(marketParams, address(this));
    }
}
