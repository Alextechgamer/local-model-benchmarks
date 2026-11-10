"""Fourth patch: thinking tokens per request from Strata's server log (opencode reports reasoning 0 for this provider)."""
import pathlib

p = pathlib.Path(r"E:\strata-dsv41\pagoda\coding-bench\tools\run_task.py")
s = p.read_text(encoding="utf-8")
rep = [
('''def engine_turns(text: str) -> list:''',
 '''THINK = re.compile(r"\\[strata\\] thinking: (\\d+) of budget")
DONE = re.compile(r"\\[strata\\] done: (\\d+) tokens")


def server_thinking(text: str) -> list:
    """Per request, from Strata's server log: the last 'thinking: N of budget' count before its 'done: N tokens'
    line (0 when the request did not think), and the request's total output tokens."""
    out, think = [], 0
    for line in text.splitlines():
        t = THINK.search(line)
        if t:
            think = int(t.group(1))
            continue
        d = DONE.search(line)
        if d:
            out.append({"thinking": think, "output": int(d.group(1))})
            think = 0
    return out


def engine_turns(text: str) -> list:'''),
('''        info["nan_drops"] = slog.count("numbers went non-finite")
''', '''        info["nan_drops"] = slog.count("numbers went non-finite")
        thinking = server_thinking(slog)
        info["thinking_per_request"] = [t["thinking"] for t in thinking]
        info["thinking_total"] = sum(t["thinking"] for t in thinking)
        info["thinking_max"] = max((t["thinking"] for t in thinking), default=0)
'''),
]
for a, b in rep:
    assert s.count(a) == 1, (a[:80], s.count(a))
    s = s.replace(a, b)
p.write_bytes(s.replace("\r\n", "\n").encode("utf-8"))
print("patched")
