"""A5 counting and split rules (fixed before the A5a spike)."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("a5", Path(__file__).parents[1] / "experiments" / "a5_catalog.py")
a5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a5)

OK = {"1_witness": {"ok": True}, "3_ablation": {"ok": True}, "5_reverse": {"ok": True}}
FULL = dict(OK, **{"2_grid": {"ok": True}, "4_spot": {"ok": True}})


def g(passed, shallow=False, checks=None):
    return {"passed": passed, "shallow": shallow, "checks": checks if checks is not None else (OK if shallow else FULL)}


def test_shallow_never_counts_as_pass():
    assert a5.status([g(True), g(True)]) == "pass"
    assert a5.status([g(True), g(False, shallow=True)]) == "shallow"
    assert a5.status([g(False, shallow=True), g(False, shallow=True)]) == "shallow"
    bad = dict(OK, **{"3_ablation": {"ok": False}})
    assert a5.status([g(False, shallow=True, checks=bad), g(True)]) == "fail"
    assert a5.status([g(True), {"passed": False, "checks": {}}]) == "fail"  # no witness


def test_split_sizes_and_test_only_mechanisms():
    mechs = ["regular_vs_amt", "eitc_tests", "filing_status", "income_shifting", "phase_out"]
    fams = [{"id": f"f{i}", "mechanism": mechs[i % 5]} for i in range(20)]
    sp = a5.split(fams)
    assert len(sp["test"]) >= 8 and len(sp["val"]) == 3 and len(sp["test"]) + len(sp["val"]) + len(sp["train"]) == 20
    mech = {f["id"]: f["mechanism"] for f in fams}
    held = set(sp["test_only_mechanisms"])
    assert len(held) == 2 and not held & {mech[i] for i in sp["val"] + sp["train"]}
    assert len(set(sp["test"]) | set(sp["val"]) | set(sp["train"])) == 20
    assert a5.split(fams) == sp  # deterministic
