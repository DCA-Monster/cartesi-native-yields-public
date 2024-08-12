// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {IAssetAllocator} from "./interfaces/IAssetAllocator.sol";
import {IInputBox} from "@cartesi-rollup-contracts/inputs/IInputBox.sol";
import {IYieldBridge} from "./interfaces/IYieldBridge.sol";
import {IERC20} from "lib/forge-std/src/interfaces/IERC20.sol";

contract YieldBridge is IYieldBridge {
    IAssetAllocator public assetAllocator;
    IInputBox public inputBox;
    address public owner;

    mapping(address => IAssetAllocator) public assetAllocators;
    address[] public tokenAddresses;

    constructor(address _inputBoxAddress, address _owner) {
        inputBox = IInputBox(_inputBoxAddress);
        owner = _owner;
    }

    function setAssetAllocator(address tokenAddress, address assetAllocatorAddress) public {
        assetAllocators[tokenAddress] = IAssetAllocator(assetAllocatorAddress);
        IERC20(tokenAddress).approve(assetAllocatorAddress, type(uint256).max);
        tokenAddresses.push(tokenAddress);
    }

    function depositERC20Tokens(address tokenAddress, address dappAddress, uint256 amount, bytes memory data) public {
        IERC20(tokenAddress).transferFrom(msg.sender, address(this), amount);
        if (address(assetAllocators[tokenAddress]) != address(0)) {
            assetAllocators[tokenAddress].allocateAssets(amount);
        }
        inputBox.addInput(dappAddress, formatInput(tokenAddress, dappAddress, amount, msg.sender, data));
    }

    function withdrawERC20Tokens(address tokenAddress, uint256 amount, address recipient) public {
        require(msg.sender == owner, "Only owner can withdraw assets");
        assetAllocators[tokenAddress].withdrawAssets(amount, recipient);
    }

    function formatInput(
        address tokenAddress,
        address dappAddress,
        uint256 amount,
        address recipient,
        bytes memory data
    ) public pure returns (bytes memory) {
        return abi.encode(tokenAddress, dappAddress, amount, recipient, data);
    }

    function getTokenBalances() public view returns (address[] memory, uint256[] memory) {
        uint256[] memory balances = new uint256[](tokenAddresses.length);
        for (uint256 i = 0; i < tokenAddresses.length; i++) {
            balances[i] = assetAllocators[tokenAddresses[i]].getBalance();
        }
        return (tokenAddresses, balances);
    }
}
