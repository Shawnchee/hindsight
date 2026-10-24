// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.20;

// Repository-owned benign fixture: no external project, live address or attack.
contract CreditLedger {
    mapping(address => uint256) public credits;

    function add(uint256 amount) external {
        credits[msg.sender] += amount;
    }

    function remove(uint256 amount) external {
        require(credits[msg.sender] >= amount, "insufficient credit");
        credits[msg.sender] -= amount;
    }
}

contract SmokeTest {
    function testCreditAccounting() external {
        CreditLedger ledger = new CreditLedger();
        ledger.add(10);
        ledger.remove(4);
        require(ledger.credits(address(this)) == 6, "credit conservation");
    }

    function testExcessRemovalReverts() external {
        CreditLedger ledger = new CreditLedger();
        ledger.add(10);
        try ledger.remove(11) {
            revert("excess removal succeeded");
        } catch {}
        require(ledger.credits(address(this)) == 10, "revert preserves credit");
    }
}
