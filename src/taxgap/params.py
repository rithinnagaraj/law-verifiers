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


def _clear_path(path: str) -> None:
    """Clear the instant cache of every node from the root down to `path`.

    Parameter.update() clears caches by walking `.parent`, but a scale
    bracket has no parent link, so for scale parameters the walk stops at
    the bracket and every ancestor (the scale's node up to the root) keeps
    at-instant objects built from the old values. Found when an EITC
    switch-off (eitc.max[i].amount = 0) leaked into later current-law
    evaluations."""
    m = _BRACKET.match(path)
    base = m.group(1) if m else path
    node = pe_system().parameters
    parts = base.split(".")
    nodes = [node]
    for p in parts:
        node = node.children[p] if hasattr(node, "children") and p in node.children else getattr(node, p, None)
        if node is None:
            break
        nodes.append(node)
    if m and node is not None:
        nodes.append(node.brackets[int(m.group(2))])
    for n in nodes:
        c = getattr(n, "_at_instant_cache", None)
        if c is not None:
            c.clear()


@contextlib.contextmanager
def pe_patched(changes: Iterable[tuple[str, object]]):
    """Apply {path: value-by-year} changes to the base system, restore after.

    Each change is (path, values) where values is a dict {year: value}; a
    value holds for that calendar year. Years outside the dict keep current
    law. Restoring reinstates the original value-list objects. After both
    steps every instant cache from the root to each changed parameter is
    cleared (_clear_path), as is the system's own cache."""
    from policyengine_core.periods import period as P

    sysm = pe_system()
    saved = []
    try:
        for path, values in changes:
            node = pe_node(path)
            saved.append((path, node, node.values_list, getattr(node, "modified", False)))
            for year in sorted(values):
                node.update(period=P(f"year:{int(year)}:1"), value=values[year])
            _clear_path(path)
        sysm._parameters_at_instant_cache = {}
        yield sysm
    finally:
        for path, node, values_list, modified in reversed(saved):
            node.values_list = values_list
            node.modified = modified
            _clear_path(path)
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
