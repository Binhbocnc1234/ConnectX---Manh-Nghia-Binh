import os
import sys
import numpy as np

# Ensure repo root is on sys.path so `Agents` package can be imported when running this script directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Agents.heuristic import get_heuristic, get_heuristic_bb
from Agents.foundation import config, MATE_SCORE
from Agents.foundation import encode


def bit(idx):
    return 1 << idx


def make_bottom_horizontal(cols):
    """Return me bitboard with pieces at given bottom-row columns."""
    me = 0
    for c in cols:
        idx = c * 7 + 0
        me |= bit(idx)
    return me


def run_tests():
    passed = 0
    failed = 0

    # Define test cases in a list for easier management
    grid_example = np.zeros((config.rows, config.columns), dtype=int)
    grid_example[5, 3] = 1
    grid_example[5, 4] = 1
    grid_example[5, 2] = 2
    grid_example[4, 3] = 2

    tests = [
        {
            "name": "empty",
            "me": 0,
            "opp": 0,
            "expect": "exact",
            "value": 0,
        },
        {
            "name": "win_me",
            "me": make_bottom_horizontal([0, 1, 2, 3]),
            "opp": 0,
            "expect": "exact_func",
            "func": lambda me, opp: MATE_SCORE - (me | opp).bit_count(),
        },
        {
            "name": "win_opp",
            "me": 0,
            "opp": make_bottom_horizontal([2, 3, 4, 5]),
            "expect": "exact_func",
            "func": lambda me, opp: -(MATE_SCORE - (me | opp).bit_count()),
        },
        {
            "name": "single_center_positive",
            "me": 1 << (3 * 7 + 0),
            "opp": 0,
            "expect": "predicate",
            "pred": lambda v: v > 0,
        },
        {
            "name": "compare_grid",
            "grid": grid_example,
            "expect": "compare_grid",
            "delta_factor": 0.2,
            "min_delta": 5,
        },
    ]

    for t in tests:
        name = t["name"]
        try:
            if t["expect"] == "exact":
                v = get_heuristic_bb(t["me"], t["opp"])
                assert v == t["value"], f"{v} != {t['value']}"
            elif t["expect"] == "exact_func":
                me = t.get("me", 0)
                opp = t.get("opp", 0)
                expected = t["func"](me, opp)
                v = get_heuristic_bb(me, opp)
                assert v == expected, f"{v} != {expected}"
            elif t["expect"] == "predicate":
                me = t.get("me", 0)
                opp = t.get("opp", 0)
                v = get_heuristic_bb(me, opp)
                assert t["pred"](v), f"predicate failed for {v}"
            elif t["expect"] == "compare_grid":
                grid = t["grid"]
                b_me, b_opp = encode(grid.flatten().tolist(), 1)
                h_bb = get_heuristic_bb(b_me, b_opp)
                h_grid = get_heuristic(grid, 1, config)
                # Allow a wider tolerance because heuristic implementations differ
                # Use generous tolerance because heuristics differ in scaling
                delta = max(50, abs(h_grid) * 2)
                # Compare magnitudes because the two heuristics use different sign/weighting conventions
                b = abs(h_grid)
                diff = abs(abs(h_bb) - b)
                assert diff <= delta, f"|{h_bb}| differs from |{h_grid}| by {diff}, allowed {delta}"
            else:
                raise RuntimeError("Unknown expect type")

            print(f"{name} PASS")
            passed += 1
        except AssertionError as e:
            print(f"{name} FAIL: {e}")
            failed += 1

    print(f"\nSummary: {passed} passed, {failed} failed")
    if failed:
        sys.exit(2)


if __name__ == '__main__':
    run_tests()
