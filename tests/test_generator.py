"""Generator versions: v2 reproduces spike 1 exactly; v3 (G0 revision 1)
excludes spike 1 and pairs two provisions of one benefit."""

from taxgap.mutations.generate import OPERATORS_V3, all_families, candidates

SPIKE1 = [
    "amt_pair:brk4.SINGLE+amt_ps.SINGLE",
    "eitc_pair:eitc_inv+eitc_ps1",
    "status_pair:brk5.HEAD_OF_HOUSEHOLD+ctc_ps.HEAD_OF_HOUSEHOLD",
    "status_child:niit.HEAD_OF_HOUSEHOLD+ctc_amt",
    "scalar_pair:dep_std+niit_rt",
    "amt_pair:brk5.SEPARATE+amt_ps.SEPARATE",
    "eitc_pair:eitc_inv+eitc_prt1",
    "status_pair:brk5.HEAD_OF_HOUSEHOLD+salt.HEAD_OF_HOUSEHOLD",
    "status_child:brk5.SEPARATE+ctc_amt",
    "scalar_pair:ctc_amt+eitc_max2",
]


def test_v2_reproduces_spike1():
    assert [f.id for f in candidates(0, 2)[:10]] == SPIKE1


def test_v3_excludes_spike1_and_pairs_two_provisions():
    v3 = candidates(0, 3)
    pairs = {f.id.split(":", 1)[1] for f in v3}
    assert not pairs & {s.split(":", 1)[1] for s in SPIKE1}
    assert len(v3) == len({f.id for f in v3})
    assert {f.id.split(":", 1)[0] for f in v3} <= set(OPERATORS_V3)
    for f in v3:
        assert f.p1.key != f.p2.key
        assert f.p1.provision != f.p2.provision or f.id.startswith("ctc_phase_out:"), f.id  # CTC amount (s.24(h)) vs threshold (s.24(b))
    # round-robin: the spike covers every operator that has candidates
    ops = [f.id.split(":", 1)[0] for f in v3[:10]]
    assert set(ops) == {f.id.split(":", 1)[0] for f in v3} & set(OPERATORS_V3)


def test_all_families_finds_both_versions():
    fams = all_families(0)
    assert all(s in fams for s in SPIKE1)
    assert all(f.id in fams for f in candidates(0, 3))


def test_age_mutations_are_whole_years():
    fams = all_families(0)
    for fid in ("eitc_age:eitc_age_min+eitc_max0", "eitc_age:eitc_age_max+eitc_max0"):
        f = fams[fid]
        for m in f.magnitudes:
            for law in f.laws(m).values():
                for c in law.changes:
                    if "age" in (c.tc or ""):
                        r = law.tc_reform(2025)[c.tc][2025]
                        assert float(r) == int(r), (fid, m, r)
    lo = fams["eitc_age:eitc_age_min+eitc_max0"]
    assert lo.laws(2.0)["L1"].tc_reform(2025)["EITC_MinEligAge"][2025] == 13
    assert lo.laws(4.0)["L1"].tc_reform(2025)["EITC_MinEligAge"][2025] == 6
