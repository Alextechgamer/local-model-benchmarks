"""Phase 4 inputs: long prompts of real and generated Python code with three planted facts at 10%, 50% and 90% depth.

usage: python make_context_prompts.py
Writes context/ctx-<label>.txt and context/prompts.json (target and measured tokens, where each fact sits).
Token counts use llama.cpp's tokenizer on the Qwen3.8 GGUF; the servers' own counts are recorded in Phase 4.

Planted facts (none of these names appear anywhere else in the prompt):
  10%  module warehouse/loyalty_rules.py: LOYALTY_RATE = Decimal("0.037"), loyalty_points(amount) and
       CRATE_CAPACITY = 18
  50%  module warehouse/shelving.py: shelf_code(aisle, bay)
  90%  module warehouse/dispatch_planner.py: crates_needed(units), which rounds down (the bug)
Questions: Q1 loyalty_points(Decimal("250.00")) -> 92; Q2 shelf_code(3, 19) -> "03-33X";
           Q3 the one-line fix of crates_needed, and crates_needed(40) after it -> 3
"""
import json, pathlib, random, re, subprocess

B = pathlib.Path(r"E:\strata-tests\coding-bench")
TOK = [str(B / "tools" / "llama-b11748-vulkan-x64" / "llama-tokenize.exe"), "-m",
       r"C:\models\qwen38\Qwen\Qwen3.8-27B\Qwen3.8-27B-IQ4_XS.gguf", "--show-count", "--log-disable", "-f"]
SIZES = {"8k": 8000, "32k": 32000, "64k": 64000, "96k": 95000, "128k": 127000, "200k": 199000, "250k": 249000}
OUT = B / "context"
OUT.mkdir(exist_ok=True)

FACT_10 = '''# ===== file: warehouse/loyalty_rules.py =====
"""Loyalty points and packing constants used by the warehouse services."""
from decimal import Decimal

LOYALTY_RATE = Decimal("0.037")
CRATE_CAPACITY = 18


def loyalty_points(amount: Decimal) -> int:
    """Loyalty points earned for an order amount in dollars."""
    return int(amount * LOYALTY_RATE * 10)
'''
FACT_50 = '''# ===== file: warehouse/shelving.py =====
"""Shelf labels for the picking robots."""


def shelf_code(aisle: int, bay: int) -> str:
    """The label printed on a shelf: aisle with two digits, a dash, a two-digit bay checksum and an X."""
    return f"{aisle:02d}-{bay * 7 % 100:02d}X"
'''
FACT_90 = '''# ===== file: warehouse/dispatch_planner.py =====
"""Planning how goods leave the warehouse."""
from warehouse.loyalty_rules import CRATE_CAPACITY


def crates_needed(units: int) -> int:
    """The number of crates needed to pack all `units` (every crate holds CRATE_CAPACITY units)."""
    return units // CRATE_CAPACITY
'''
QUESTIONS = '''

Questions about the code above. Answer from the code only.
Q1: What does loyalty_points(Decimal("250.00")) return?
Q2: What does shelf_code(3, 19) return?
Q3: crates_needed has a bug: for some inputs it returns too few crates. Give the corrected return line of
    crates_needed, and what crates_needed(40) returns after your fix.

Reply with exactly three lines and nothing else:
Q1: <value>
Q2: <value>
Q3: <the corrected return line> | <value>
'''
HEAD = "Below are the source files of a large Python codebase for an online shop. Read them carefully; questions " \
       "follow at the end.\n\n"
BANNED = ("loyalty", "shelf_code", "crate", "LOYALTY", "CRATE", "dispatch_planner")

REAL = []
for f in sorted((B / "project" / "base" / "inventory_service").glob("*.py")):
    REAL.append(f"# ===== file: inventory_service/{f.name} =====\n{f.read_text(encoding='utf-8')}\n")

WORDS = ("order invoice parcel route supplier carrier ledger voucher basket shipment pallet batch zone picker tariff "
         "quota bundle manifest dock label rate fee slot window budget forecast region channel vendor promo grade "
         "lane tote cycle audit claim credit debit margin rebate cutoff").split()
VERBS = "compute build resolve merge split rank filter apply validate estimate allocate summarize normalize load".split()


def gen_module(rng: random.Random, i: int) -> str:
    """One generated module in the style of the real package: constants, a dataclass, functions with docstrings."""
    a, b, c = rng.sample(WORDS, 3)
    mod = f"{a}_{b}_{i:03d}"
    lines = [f"# ===== file: services/{mod}.py =====", f'"""{a.title()} and {b} handling for the {c} service."""',
             "from __future__ import annotations", "", "from dataclasses import dataclass, field",
             "from decimal import Decimal", ""]
    for _ in range(rng.randint(2, 4)):
        name = f"{rng.choice(WORDS).upper()}_{rng.choice(WORDS).upper()}_{rng.randint(1, 99)}"
        val = rng.choice([str(rng.randint(2, 500)), f'Decimal("{rng.randint(1, 99)}.{rng.randint(0, 99):02d}")',
                          f'"{rng.choice(WORDS)}-{rng.randint(100, 999)}"'])
        lines.append(f"{name} = {val}")
    cls = f"{a.title()}{b.title()}"
    lines += ["", "", "@dataclass", f"class {cls}:", f"    {c}_id: str", f"    {a}_count: int = 0",
              f"    {b}_amount: Decimal = Decimal(\"0\")", f"    tags: list[str] = field(default_factory=list)", "",
              f"    def total(self) -> Decimal:", f"        return self.{b}_amount * self.{a}_count", ""]
    for _ in range(rng.randint(3, 6)):
        v, x, y = rng.choice(VERBS), rng.choice(WORDS), rng.choice(WORDS)
        fn = f"{v}_{x}_{y}"
        k = rng.randint(2, 40)
        body = rng.choice([
            [f"    out = []", f"    for item in items:", f"        if item.{a}_count >= {k}:",
             f"            out.append(item)", f"    return sorted(out, key=lambda it: it.{c}_id)"],
            [f"    total = Decimal(\"0\")", f"    for item in items:", f"        total += item.total()",
             f"    return total.quantize(Decimal(\"0.01\"))"],
            [f"    seen = {{}}", f"    for item in items:", f"        seen[item.{c}_id] = seen.get(item.{c}_id, 0) + item.{a}_count",
             f"    return {{key: value for key, value in seen.items() if value % {k} != 0}}"],
            [f"    if not items:", f"        raise ValueError(\"no {x} to {v}\")",
             f"    best = max(items, key=lambda it: (it.{b}_amount, it.{c}_id))", f"    return best.{c}_id"],
        ])
        lines += ["", "", f"def {fn}(items: list[{cls}]) -> object:",
                  f'    """{v.title()} the {x} records by {y}; items with fewer than {k} units are treated as '
                  f'{rng.choice(WORDS)}."""'] + body
    text = "\n".join(lines) + "\n\n"
    assert not any(w in text for w in BANNED)
    return text


def count(text: str) -> int:
    p = OUT / "_count.txt"
    p.write_text(text, encoding="utf-8")
    r = subprocess.run(TOK + [str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return int(re.findall(r"\d+", (r.stdout + r.stderr).strip().splitlines()[-1])[-1])


rng = random.Random(20261020)
GEN = [gen_module(rng, i) for i in range(1200)]
# average tokens per generated module, to plan sizes
sample_tokens = count("".join(GEN[:40])) / 40
real_tokens = count("".join(REAL))
fact_tokens = count(FACT_10 + FACT_50 + FACT_90)
fixed = count(HEAD + QUESTIONS) + fact_tokens
meta = {"sample_tokens_per_generated_module": round(sample_tokens, 1), "real_code_tokens": real_tokens, "prompts": {}}
for label, target in SIZES.items():
    body_budget = target - fixed
    pad = []
    used = 0
    for r in REAL:                                   # real code first (as much as fits), then generated modules
        t = len(r) / 3.3
        if used + t > body_budget:
            break
        pad.append(r); used += t
    gi = 0
    while used < body_budget * 0.97:
        pad.append(GEN[gi]); used += sample_tokens; gi += 1
    rng2 = random.Random(len(pad))
    rng2.shuffle(pad)
    def assemble(pad):
        n = len(pad)
        cut = [round(n * 0.10), round(n * 0.50), round(n * 0.90)]
        parts = pad[:cut[0]] + [FACT_10] + pad[cut[0]:cut[1]] + [FACT_50] + pad[cut[1]:cut[2]] + [FACT_90] + pad[cut[2]:]
        return HEAD + "".join(parts) + QUESTIONS, parts
    text, parts = assemble(pad)
    tokens = count(text)
    # trim or extend with generated modules until within 1.5% of the target
    for _ in range(12):
        if abs(tokens - target) <= target * 0.015:
            break
        step = max(1, int(abs(tokens - target) / sample_tokens))
        if tokens > target:
            pad = pad[:-step]
        else:
            pad = pad + GEN[gi:gi + step]; gi += step
        text, parts = assemble(pad)
        tokens = count(text)
    # where each fact starts, as a fraction of the prompt's tokens
    pos = {}
    for name, fact in (("fact_10", FACT_10), ("fact_50", FACT_50), ("fact_90", FACT_90)):
        before = text[:text.index(fact)]
        pos[name] = round(count(before) / tokens, 3)
    (OUT / f"ctx-{label}.txt").write_text(text, encoding="utf-8")
    meta["prompts"][label] = {"target_tokens": target, "tokens": tokens, "files": len(pad) + 3, "fact_depth": pos}
    print(label, meta["prompts"][label], flush=True)
(OUT / "prompts.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
