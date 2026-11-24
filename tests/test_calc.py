"""Calculator layer: parameter patching is exact, batches are consistent
(v1 findings F8, F12), the memo returns what a fresh evaluation returns."""

import copy

import pytest

from taxgap.calc import pe
from taxgap.calc.evaluate import clear_memo, evaluate
from taxgap.law import CURRENT_LAW, Change, by_status
from taxgap.model import Asset, Person, TaxUnit, compile_returns
from taxgap.params import pe_patched, pe_value
from helpers import H, couple, parent_child, single


def _reform_tax(hh, pe_dict, year):
    """PolicyEngine tax under a Reform system (the reference)."""
    from policyengine_core.reforms import Reform
    from policyengine_us import CountryTaxBenefitSystem, Simulation

    from taxgap.calc.pe import _situation

    sysm = CountryTaxBenefitSystem(reform=Reform.from_dict({k: {f"{year}-01-01.{year}-12-31": v} for k, v in pe_dict.items()}, country_id="us"))
    rs = compile_returns(hh, "x", year)
    sim = Simulation(situation=_situation(rs, CURRENT_LAW, {}), tax_benefit_system=sysm)
    return [float(x) for x in sim.calculate("income_tax", str(year))]


def test_patch_matches_reform_and_restores():
    hh = couple(150_000, 120_000, kids=(4, 9))
    hh.tax_units = [TaxUnit("t", "a", dependents=["k0", "k1"], filing_status="SEPARATE"), TaxUnit("t_s", "b", filing_status="SEPARATE")]
    year = 2025
    changes = {
        "gov.irs.deductions.standard.amount.SEPARATE": 2 * pe_value("gov.irs.deductions.standard.amount.SEPARATE", year),
        "gov.irs.credits.ctc.phase_out.threshold.SEPARATE": 400_000.0,
        "gov.irs.income.bracket.thresholds.3.SEPARATE": 1.5 * pe_value("gov.irs.income.bracket.thresholds.3.SEPARATE", year),
    }
    law = CURRENT_LAW.plus(
        by_status("gov.irs.deductions.standard.amount", "STD", "SEPARATE", "scale", 2.0),
        by_status("gov.irs.credits.ctc.phase_out.threshold", "CTC_ps", "SEPARATE", "set", 400_000.0),
        by_status("gov.irs.income.bracket.thresholds.3", "II_brk3", "SEPARATE", "scale", 1.5),
    )
    rs = compile_returns(hh, "x", year)
    before = [r.fed_tax for r in pe.evaluate(rs, CURRENT_LAW).values()]
    patched = [r.fed_tax for r in pe.evaluate(rs, law).values()]
    after = [r.fed_tax for r in pe.evaluate(rs, CURRENT_LAW).values()]
    assert patched == pytest.approx(_reform_tax(hh, changes, year), abs=0.5)
    assert after == pytest.approx(before, abs=0.01)
    assert patched != pytest.approx(before, abs=1)


def test_scale_patch_takes_effect_and_restores_after_caching():
    # Scale brackets have no parent link: caches above them must be cleared
    # explicitly, both when patching and when restoring (found in A2 testing:
    # the whitelist's EITC switch-off leaked into later current-law results).
    from taxgap.law import PROVISIONS

    hh = H("e", {"a": Person("a", 30, wages=20_000, hours=2080), "k": Person("k", 6)}, TaxUnit("t", "a", dependents=["k"]))
    rs = compile_returns(hh, "x", 2025)
    cur = pe.evaluate(rs, CURRENT_LAW)["x.0"].fed_tax  # primes every instant cache
    off = pe.evaluate(rs, CURRENT_LAW.without("eitc"))["x.0"].fed_tax
    again = pe.evaluate(rs, CURRENT_LAW)["x.0"].fed_tax
    assert off - cur > 3_000  # the patch took effect although caches were primed
    assert again == pytest.approx(cur, abs=0.01)  # and the restore is complete
    for name in ("retirement_contributions", "ctc", "head_of_household"):
        pe.evaluate(rs, CURRENT_LAW.without(name))
        assert pe.evaluate(rs, CURRENT_LAW)["x.0"].fed_tax == pytest.approx(cur, abs=0.01), name


def test_both_calculators_see_the_change():
    hh = couple(120_000, 100_000)
    hh.tax_units = [TaxUnit("t", "a", filing_status="SEPARATE"), TaxUnit("t_s", "b", filing_status="SEPARATE")]
    law = CURRENT_LAW.plus(by_status("gov.irs.deductions.standard.amount", "STD", "SEPARATE", "scale", 2.0))
    for year in (2024, 2026):
        h = copy.deepcopy(hh)
        h.year = year
        r0, r1 = evaluate([h], CURRENT_LAW, fresh=True)[0], evaluate([h], law, fresh=True)[0]
        assert r0.pe - r1.pe == pytest.approx(r0.tc - r1.tc, abs=2)
        assert r0.pe - r1.pe > 1_000


def test_itemize_forced_does_not_leak_to_free_returns():
    # F8: forcing itemization on one return must not change another's choice.
    a = single(250_000, hid="a")
    a.people["a"].mortgage_interest = 40_000
    b = copy.deepcopy(a)
    b.tax_units[0].itemize = False
    alone = evaluate([a], CURRENT_LAW, fresh=True)[0].pe
    mixed = evaluate([b, a], CURRENT_LAW, fresh=True)[1].pe
    assert mixed == pytest.approx(alone, abs=0.5)


def test_duplicates_in_one_batch():
    # F12: two different households sharing an id, and two copies of one, in one batch.
    a = single(50_000, hid="same")
    b = single(90_000, hid="same")
    r = evaluate([a, b, a, parent_child(hid="same")], CURRENT_LAW, fresh=True)
    assert r[0].pe == pytest.approx(4_016, abs=1) and r[2].pe == pytest.approx(r[0].pe)
    assert r[1].pe != pytest.approx(r[0].pe, abs=100)
    assert r[3].pe == pytest.approx(66_017 + 6_220, abs=2)


def test_memo_equals_fresh():
    clear_memo()
    hhs = [single(w, hid=f"s{w}") for w in (20_000, 50_000, 150_000)] + [parent_child(), couple(80_000, 0, kids=(3,))]
    memo = evaluate(hhs, CURRENT_LAW) + evaluate(hhs, CURRENT_LAW)
    fresh = [evaluate([h], CURRENT_LAW, fresh=True)[0] for h in hhs]
    for m, f in zip(memo, fresh + fresh):
        assert m.pe == pytest.approx(f.pe, abs=0.01) and m.tc == pytest.approx(f.tc, abs=0.01)


def test_kiddie_variant_keeps_parent_salt():
    # Itemizing parent in a taxing state: both calculators agree on the total.
    # (The Form 8615 component differs: Tax-Calculator applies the child AMT
    # limit on the child's own return and PolicyEngine does not, F3.)
    hh = parent_child(wages=400_000, interest=30_000)
    hh.state = "CA"
    hh.people["p"].mortgage_interest = 30_000
    r = evaluate([hh], CURRENT_LAW, fresh=True)[0]
    assert r.kiddie_pe > 0 and r.kiddie_tc > 0 and r.pe == pytest.approx(r.tc, abs=5)


def test_separate_filers_living_together_alignment():
    # EITC (s.32(d)) and child care credit (s.21(e)(2)) are not available to
    # a spouse filing separately who lives with the other spouse.
    hh = couple(30_000, 0, kids=(4, 7))
    hh.people["a"].childcare = 4_000
    hh.tax_units = [TaxUnit("t", "a", dependents=["k0", "k1"], filing_status="SEPARATE"), TaxUnit("t_s", "b", filing_status="SEPARATE")]
    r = evaluate([hh], CURRENT_LAW, fresh=True)[0]
    assert r.pe == pytest.approx(r.tc, abs=2)


def _parent(wages, **kw):
    return H("p2", {"a": Person("a", 30, wages=wages, hours=2080, **kw), "k0": Person("k0", 9), "k1": Person("k1", 5)},
             TaxUnit("t", "a", dependents=["k0", "k1"], filing_status="HEAD_OF_HOUSEHOLD"))


@pytest.mark.parametrize("status", ["HEAD_OF_HOUSEHOLD", "SINGLE"])
def test_care_expenses_without_imputed_subsidy(status):
    # A2: PolicyEngine subtracted an imputed child care subsidy (4,680 -> 104
    # of expenses); Tax-Calculator has none. Both now see expenses as paid.
    hh = _parent(30_600, childcare=4_680)
    hh.tax_units[0].filing_status = status
    r = evaluate([hh], CURRENT_LAW, fresh=True)[0]
    assert r.pe + r.pe_only == pytest.approx(r.tc, abs=2)


def test_savers_credit_excluded_when_not_usable():
    # A2: a low earner with no tax left before credits; adding the computed
    # saver's credit back made PolicyEngine's tax too high.
    hh = _parent(28_000, k401=2_000)
    r = evaluate([hh], CURRENT_LAW, fresh=True)[0]
    assert r.pe_only == 0 and r.pe == pytest.approx(r.tc, abs=2)
