"""Correctness smoke test for one running server: tool calling + a short coding answer. Prints JSON, appends to a file.

usage: python smoke.py --url http://127.0.0.1:8090/v1 --tag NAME [--reps 3] [--out results/smoke.jsonl]
Checks per repetition:
  tool_call   the model calls read_file with {"path": "src/app/config.py"} (a parsed tool call, not text)
  tool_typed  the model calls run_tests with path "tests/test_orders.py" and verbose true as a JSON boolean
  tool_result after a tool result is given, the final answer contains the value from it (MAX_RETRIES = 7)
  code        a merge_intervals function from the answer passes 8 asserts when executed
"""
import argparse, json, re, time, urllib.request, uuid

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--tag", required=True)
ap.add_argument("--reps", type=int, default=3)
ap.add_argument("--max-tokens", type=int, default=12000)
ap.add_argument("--out", default=r"E:\strata-tests\coding-bench\results\smoke.jsonl")
a = ap.parse_args()

TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a text file from the repository.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "repo-relative path"}},
                    "required": ["path"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run pytest on one test file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"},
                                                     "verbose": {"type": "boolean"}},
                    "required": ["path", "verbose"]}}},
]


def post(body):
    body = dict(body, model="local", max_tokens=a.max_tokens, stream=False, reasoning_effort="medium")
    req = urllib.request.Request(a.url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer none"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())


def calls(resp):
    m = resp["choices"][0]["message"]
    out = []
    for c in m.get("tool_calls") or []:
        args = c["function"]["arguments"]
        out.append((c["function"]["name"], json.loads(args) if isinstance(args, str) else args, c.get("id")))
    return out, m


def nonce():
    return f"(session {uuid.uuid4().hex[:8]}) "


def rep():
    res = {}
    # 1. simple tool call, then the result turn
    msgs = [{"role": "system", "content": nonce() + "You are a coding agent. Use the tools to inspect the repository."},
            {"role": "user", "content": "What is the value of MAX_RETRIES in src/app/config.py? Read the file to find out."}]
    r1 = post({"messages": msgs, "tools": TOOLS})
    c1, m1 = calls(r1)
    res["tool_call"] = bool(c1) and c1[0][0] == "read_file" and c1[0][1].get("path", "").strip("./") == "src/app/config.py"
    if c1:
        cid = c1[0][2] or "call_1"
        msgs += [{"role": "assistant", "content": m1.get("content") or "",
                  "tool_calls": [{"id": cid, "type": "function", "function": {"name": c1[0][0],
                                  "arguments": json.dumps(c1[0][1])}}]},
                 {"role": "tool", "tool_call_id": cid,
                  "content": "import os\n\nTIMEOUT_S = 30\nMAX_RETRIES = 7\nBACKOFF = 1.5\n"}]
        r2 = post({"messages": msgs, "tools": TOOLS})
        ans = r2["choices"][0]["message"].get("content") or ""
        res["tool_result"] = bool(re.search(r"\b7\b", ans)) and not (r2["choices"][0]["message"].get("tool_calls"))
    else:
        res["tool_result"] = False
    # 2. typed arguments
    msgs = [{"role": "system", "content": nonce() + "You are a coding agent."},
            {"role": "user", "content": "Run the tests in tests/test_orders.py with verbose output."}]
    c3, _ = calls(post({"messages": msgs, "tools": TOOLS}))
    res["tool_typed"] = bool(c3) and c3[0][0] == "run_tests" and c3[0][1].get("path", "").strip("./") == \
        "tests/test_orders.py" and c3[0][1].get("verbose") is True
    if not res["tool_typed"]:
        res["tool_typed_got"] = [(n, args) for n, args, _ in c3]
    # 3. short coding answer, executed
    msgs = [{"role": "user", "content": nonce() + "Write a Python function merge_intervals(intervals) that takes a list "
             "of [start, end] integer pairs (in any order, possibly empty) and returns a new list of merged, sorted, "
             "non-overlapping intervals; intervals that touch (end == next start) are merged. Do not modify the input "
             "list. Reply with one python code block only."}]
    ans = post({"messages": msgs})["choices"][0]["message"].get("content") or ""
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", ans, re.S)
    ok = False
    if blocks:
        ns = {}
        try:
            exec(blocks[-1], ns)
            f = ns["merge_intervals"]
            assert f([]) == []
            assert f([[1, 3]]) == [[1, 3]]
            assert f([[1, 3], [2, 6], [8, 10], [15, 18]]) == [[1, 6], [8, 10], [15, 18]]
            assert f([[1, 4], [4, 5]]) == [[1, 5]]
            assert f([[5, 6], [1, 2]]) == [[1, 2], [5, 6]]
            assert f([[1, 10], [2, 3], [4, 5]]) == [[1, 10]]
            assert f([[6, 8], [1, 9], [2, 4], [4, 7]]) == [[1, 9]]
            src = [[3, 4], [1, 2]]; f(src); assert src == [[3, 4], [1, 2]]
            ok = True
        except Exception as e:
            import traceback
            res["code_error"] = f"{type(e).__name__}: {e}"[:200]
            res["code_failed_line"] = traceback.format_exc().strip().splitlines()[-2][:200]
            res["code_answer"] = ans[-3000:]
    else:
        res["code_answer"] = ans[-3000:]
    res["code"] = ok
    return res


rows = []
for i in range(a.reps):
    t0 = time.time()
    try:
        r = rep()
    except Exception as e:
        r = {"error": f"{type(e).__name__}: {e}"[:300]}
    # smoke_version 2: the coding prompt says "Do not modify the input list" (v1 tested that without saying it)
    r.update(tag=a.tag, rep=i + 1, wall_s=round(time.time() - t0, 1), smoke_version=2)
    rows.append(r)
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(r) + "\n")
    print(json.dumps(r), flush=True)
keys = ["tool_call", "tool_typed", "tool_result", "code"]
score = {k: sum(1 for r in rows if r.get(k)) for k in keys}
print("SMOKE", a.tag, json.dumps(score), "of", a.reps)
