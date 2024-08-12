// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

interface IAssetAllocator {
    function allocateAssets(uint256 amount) external;
    function withdrawAssets(uint256 amount, address recipient) external;
    function getBalance() external view returns (uint256);
}
