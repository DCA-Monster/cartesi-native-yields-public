// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {IInputBox} from "@cartesi-rollup-contracts/inputs/IInputBox.sol";
import {IYieldBridge} from "./interfaces/IYieldBridge.sol";

contract InputBoxWrapper is IInputBox {
    IInputBox public inputBox;
    IYieldBridge public yieldBridge;

    constructor(address inputBoxAddress) {
        inputBox = IInputBox(inputBoxAddress);
    }

    function setYieldBridge(address yieldBridgeAddress) public {
        yieldBridge = IYieldBridge(yieldBridgeAddress);
    }

    function addInput(address _dapp, bytes calldata _input) public returns (bytes32) {
        (address[] memory tokenAddresses, uint256[] memory balances) = yieldBridge.getTokenBalances();
        bytes memory data = abi.encode(msg.sender, tokenAddresses, balances, _input);
        return inputBox.addInput(_dapp, data);
    }

    function getNumberOfInputs(address _dapp) public view returns (uint256) {
        return inputBox.getNumberOfInputs(_dapp);
    }

    function getInputHash(address _dapp, uint256 _index) public view returns (bytes32) {
        return inputBox.getInputHash(_dapp, _index);
    }
}
