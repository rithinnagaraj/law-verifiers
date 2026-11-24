"""Calculator parameters: read current law, and apply a law's changes.

PolicyEngine: one base tax-benefit system per process. A law is applied by
patching the parameter tree in place and restoring the original value lists
afterwards (`pe_patched`). Building a PolicyEngine Reform system instead
takes 10-50 s and ~0.6 GB per law; the patch is exact (tested against
Reform in tests/test_params.py).

Tax-Calculator: a fresh Policy per evaluation; changes are given per year.
"""

from __future__ import annotations

import contextlib
import re
from functools import lru_cache
from typing import Iterable

# Years a PolicyEngine patch covers (horizon, 10-year sensitivity, margin).
PATCH_YEARS = range(2018, 2037)

MARS_ORDER = ("SINGLE", "JOINT", "SEPARATE", "HEAD_OF_HOUSEHOLD", "SURVIVING_SPOUSE")


@lru_cache(maxsize=1)
def pe_system():
    import warnings

    warnings.filterwarnings("ignore")
    from policyengine_us import CountryTaxBenefitSystem

    return CountryTaxBenefitSystem()


_BRACKET = re.compile(r"^(.*)\[(\d+)\]\.(amount|threshold|rate)$")


def pe_node(path: str):
    """A PolicyEngine parameter by path; scale brackets as `path[i].amount`."""
    m = _BRACKET.match(path)
    root = pe_system().parameters
    if m:
        scale = root.get_child(m.group(1))
        return getattr(scale.brackets[int(m.group(2))], m.group(3))
    return root.get_child(path)


def pe_value(path: str, year: int) -> float:
    v = pe_node(path)(f"{year}-01-01")
    return float(v) if not isinstance(v, bool) else v


@contextlib.contextmanager
def pe_patched(changes: Iterable[tuple[str, object]]):
    """Apply {path: value-by-year} changes to the base system, restore after.

    Each change is (path, values) where values is a dict {year: value}; a
    value holds for that calendar year. Years outside the dict keep current
    law. Restoring reinstates the original value-list objects and clears
    every instant cache on the way to the root."""
    from policyengine_core.periods import period as P

    sysm = pe_system()
    saved = []
    try:
        for path, values in changes:
            node = pe_node(path)
            saved.append((node, node.values_list, getattr(node, "modified", False)))
            for year in sorted(values):
                node.update(period=P(f"year:{int(year)}:1"), value=values[year])
        sysm._parameters_at_instant_cache = {}
        yield sysm
    finally:
        for node, values_list, modified in reversed(saved):
            node.values_list = values_list
            node.modified = modified
            node.parent.clear_parent_cache()
        sysm._parameters_at_instant_cache = {}


# ---------------------------------------------------------------------------
# Tax-Calculator
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _tc_policy_proto():
    import taxcalc as tc

    return tc.Policy()


def tc_value(name: str, year: int):
    """Current-law Tax-Calculator parameter value for `year` (a list for
    MARS- or kid-indexed parameters)."""
    import copy

    pol = copy.deepcopy(_tc_policy_proto())
    pol.set_year(year)
    v = getattr(pol, name)[0]
    try:
        return [float(x) for x in v]
    except TypeError:
        return float(v)
