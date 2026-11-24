"""Calculator adapters and batched evaluation."""

from dataclasses import dataclass


@dataclass
class ReturnResult:
    key: str
    fed_tax: float  # federal income tax after all credits (refundable included)
    regular_tax: float  # before credits, ordinary + preferential rates, no AMT
    amt: float
    taxable_income: float
    pe_only_credits: float = 0.0  # federal credits only PolicyEngine computes (saver's)
    salt: float = 0.0  # state and local income tax (PolicyEngine), for Tax-Calculator
