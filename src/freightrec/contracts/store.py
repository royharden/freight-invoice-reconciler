"""Immutable-by-copy in-memory policy collection; persistence belongs to callers."""
from copy import deepcopy
from .model import validate_contract
from .resolver import select_contract


class ContractStore:
    def __init__(self, contracts: list[dict]):
        self._contracts = deepcopy(contracts)
        ids = []
        for contract in self._contracts:
            validate_contract(contract)
            ids.append(contract["contract_id"])
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate contract IDs")

    def resolve(self, shipment: dict) -> dict:
        return deepcopy(select_contract(self._contracts, shipment))
