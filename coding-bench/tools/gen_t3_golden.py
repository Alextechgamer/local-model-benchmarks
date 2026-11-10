"""Generate hidden/T3/test_t3_golden.py: compute_order_total results and errors from the base code, as literals.

usage: python gen_t3_golden.py   (imports the base package from project/base)
"""
import itertools, json, pathlib, sys

B = pathlib.Path(r"E:\strata-tests\coding-bench")
sys.path[:0] = [str(B / "project" / "base"), str(B / "hidden" / "common")]
from _hx import CUSTOMERS, customer, lines, world  # noqa: E402
from inventory_service.models import OrderLine  # noqa: E402
from inventory_service.pricing import compute_order_total  # noqa: E402

ITEMS = [
    [("TOO-0001", 1)], [("TOO-0002", 3)], [("GAR-0001", 2), ("LIT-0001", 1)], [("KIT-0001", 10)],
    [("KIT-0001", 9), ("GAR-0002", 12)], [("LIT-0001", 4), ("KIT-0002", 2), ("TOO-0001", 3)], [("GAR-0001", 6)],
    [("KIT-0002", 1)],
]
COUPONS = [None, "SAVE10", " flat5 ", "BIG25", "BOGUS"]
REGIONS = [None, "US-NY", "MARS"]
cat, *_ = world()


def run(cid, items, coupon, region, raw_lines=None):
    try:
        ls = raw_lines if raw_lines is not None else lines(cat, *items)
        b = compute_order_total(ls, cat, customer(cid), coupon, region)
        return {"ok": {k: str(v) for k, v in b.to_dict().items()},
                "lines": [[d["sku"], d["quantity"], str(d["gross"]), str(d["discount"]), str(d["net"]), str(d["percent"])]
                          for d in b.lines]}
    except Exception as e:
        return {"error": [type(e).__name__, str(e)]}


cases = {}
for (cid, *_), (ii, items), coupon, region in itertools.product(CUSTOMERS, enumerate(ITEMS), COUPONS, REGIONS):
    if region == "MARS" and coupon not in (None, "BOGUS"):
        continue
    cases.setdefault(cid, []).append([ii, coupon, region, run(cid, items, coupon, region)])
# odd inputs: zero / negative quantities, unknown SKU, empty order, an unknown SKU with zero quantity
odd = []
for name, raw in [("zero", [OrderLine("TOO-0001", 0, cat.get("TOO-0001").price)]),
                  ("negative_second", [OrderLine("TOO-0001", 1, cat.get("TOO-0001").price), OrderLine("KIT-0001", -2, cat.get("KIT-0001").price)]),
                  ("unknown_sku", [OrderLine("ZZZ-0001", 1, cat.get("TOO-0001").price)]),
                  ("unknown_sku_zero_qty", [OrderLine("ZZZ-0001", 0, cat.get("TOO-0001").price)]),
                  ("empty", []),
                  ("custom_price", [OrderLine("TOO-0002", 2, cat.get("TOO-0002").price / 3)])]:
    odd.append([name, run("C2", None, None, None, raw)])
code = ['"""Task 3: compute_order_total must behave exactly as before the refactor (generated from the starting code)."""',
        "import json", "", "import pytest", "", "from _hx import customer, lines, world", "",
        f"ITEMS = {json.dumps(ITEMS)}", f"CASES = json.loads({json.dumps(json.dumps(cases))})",
        f"ODD = json.loads({json.dumps(json.dumps(odd))})", "",
        "",
        "def check(got_fn, expected):",
        "    try:",
        "        b = got_fn()",
        "    except Exception as e:",
        "        assert 'error' in expected, f'unexpected {type(e).__name__}: {e}'",
        "        assert [type(e).__name__, str(e)] == expected['error']",
        "        return",
        "    assert 'ok' in expected, f\"expected {expected.get('error')}\"",
        "    assert {k: str(v) for k, v in b.to_dict().items()} == expected['ok']",
        "    assert [[d['sku'], d['quantity'], str(d['gross']), str(d['discount']), str(d['net']), str(d['percent'])]",
        "            for d in b.lines] == expected['lines']",
        "", ""]
for cid in cases:
    code += [f"def test_keep_golden_{cid}():",
             "    from inventory_service.pricing import compute_order_total",
             "    cat, *_ = world()",
             f"    for ii, coupon, region, expected in CASES[{cid!r}]:",
             "        items = [tuple(x) for x in ITEMS[ii]]",
             f"        check(lambda: compute_order_total(lines(cat, *items), cat, customer({cid!r}), coupon, region), expected)",
             "", ""]
code += ["def test_keep_golden_odd_inputs():",
         "    from inventory_service.models import OrderLine",
         "    from inventory_service.pricing import compute_order_total",
         "    cat, *_ = world()",
         "    raw = {'zero': [OrderLine('TOO-0001', 0, cat.get('TOO-0001').price)],",
         "           'negative_second': [OrderLine('TOO-0001', 1, cat.get('TOO-0001').price), OrderLine('KIT-0001', -2, cat.get('KIT-0001').price)],",
         "           'unknown_sku': [OrderLine('ZZZ-0001', 1, cat.get('TOO-0001').price)],",
         "           'unknown_sku_zero_qty': [OrderLine('ZZZ-0001', 0, cat.get('TOO-0001').price)],",
         "           'empty': [],",
         "           'custom_price': [OrderLine('TOO-0002', 2, cat.get('TOO-0002').price / 3)]}",
         "    for name, expected in ODD:",
         "        check(lambda: compute_order_total(raw[name], cat, customer('C2')), expected)",
         "", ""]
out = B / "hidden" / "T3" / "test_t3_golden.py"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(code), encoding="utf-8")
n = sum(len(v) for v in cases.values())
print(f"wrote {out}: {n} cases in {len(cases)} customer tests + {len(odd)} odd inputs; "
      f"errors: {sum(1 for v in cases.values() for c in v if 'error' in c[3])}")
