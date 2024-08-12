// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

interface IYieldBridge {
    function depositERC20Tokens(address tokenAddress, address dappAddress, uint256 amount, bytes memory data)
        external;

    function getTokenBalances() external view returns (address[] memory, uint256[] memory);
}
