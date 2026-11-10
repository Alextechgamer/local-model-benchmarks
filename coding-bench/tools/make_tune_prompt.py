"""Build the fixed ~16K-token tuning prompt from real Python source (Strata's serve/ code, read only).

usage: python make_tune_prompt.py <out.txt> <target_tokens> <tokenizer_cmd...>
The tokenizer command gets the file path appended and must print the token count as the last number.
"""
import pathlib, re, subprocess, sys

out, target = pathlib.Path(sys.argv[1]), int(sys.argv[2])
tok_cmd = sys.argv[3:]
src = sorted(pathlib.Path(r"C:\Users\user\Strata\serve").glob("*.py"))
HEAD = ("Below is the source of several Python modules from an inference server. Read all of it, then write a "
        "thorough code review: for each module, list concrete bugs, risky edge cases and refactoring ideas, "
        "quoting the function names. Be long and detailed; do not stop early.\n\n")
TAIL = "\n\nNow write the review, module by module."


def build(chars):
    body, n = [], 0
    for f in src:
        t = f.read_text(encoding="utf-8", errors="replace")
        piece = f"# ===== file: serve/{f.name} =====\n{t}\n"
        if n + len(piece) > chars:
            piece = piece[: chars - n]
        body.append(piece); n += len(piece)
        if n >= chars:
            break
    return HEAD + "".join(body) + TAIL


def count(text):
    out.write_text(text, encoding="utf-8")
    r = subprocess.run(tok_cmd + [str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    nums = re.findall(r"\d+", (r.stdout + r.stderr).strip().splitlines()[-1])
    return int(nums[-1])


chars = target * 3
for _ in range(8):
    n = count(build(chars))
    print(f"chars={chars} tokens={n}")
    if abs(n - target) <= target * 0.005:
        break
    chars = int(chars * target / n)
print("final tokens", n)
