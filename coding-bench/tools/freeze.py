"""Write FROZEN.txt (SHA-256 of every file under tasks/ and hidden/, plus the scorer and references for the record),
or check the current files against it.

usage: python freeze.py write | check
"""
import hashlib, pathlib, sys

B = pathlib.Path(__file__).resolve().parents[1]       # this coding-bench folder (was a fixed E:\strata-tests path)
FROZEN_SETS = ["tasks", "hidden"]
RECORD_SETS = ["reference", "score.py", "validate.py"]


def files(entry):
    p = B / entry
    items = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
    return [x for x in items if "__pycache__" not in x.parts and x.suffix != ".pyc"]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def table(sets):
    return {str(f.relative_to(B)).replace("\\", "/"): digest(f) for s in sets for f in files(s)}


if sys.argv[1] == "write":
    if (B / "FROZEN.txt").exists():
        sys.exit("FROZEN.txt exists already")
    frozen, record = table(FROZEN_SETS), table(RECORD_SETS)
    lines = ["# FROZEN: tasks and hidden tests. Do not change these files; tools/freeze.py check verifies them.",
             f"# {len(frozen)} frozen files"]
    lines += [f"{h}  {p}" for p, h in frozen.items()]
    lines += ["", f"# RECORD (not frozen, for reference): {len(record)} files"]
    lines += [f"{h}  {p}" for p, h in record.items()]
    (B / "FROZEN.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"froze {len(frozen)} files, recorded {len(record)}")
else:
    want = {}
    for line in (B / "FROZEN.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            if line.startswith("# RECORD"):
                break
            continue
        h, p = line.split("  ", 1)
        want[p] = h
    now = table(FROZEN_SETS)
    changed = [p for p in want if now.get(p) != want[p]]
    added = [p for p in now if p not in want]
    if changed or added:
        print(f"MISMATCH changed={changed} added={added}")
        sys.exit(1)
    print(f"OK: {len(want)} frozen files unchanged")
