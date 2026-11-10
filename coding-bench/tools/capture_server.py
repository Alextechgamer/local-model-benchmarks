"""A fake OpenAI-compatible server that records each /v1/chat/completions request body and answers "Done.".

usage: python capture_server.py <port> <out.jsonl>
Used once to see exactly what opencode sends (system prompt, tools, sampling fields) before the real runs.
"""
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, OUT = int(sys.argv[1]), sys.argv[2]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"object": "list", "data": [{"id": "probe", "object": "model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps({"path": self.path, "t": time.time(), "body": req}) + "\n")
        if req.get("stream"):
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for d in ({"role": "assistant", "content": "Done."}, {}):
                ch = {"id": "x", "object": "chat.completion.chunk", "created": int(time.time()), "model": "probe",
                      "choices": [{"index": 0, "delta": d, "finish_reason": None if d else "stop"}]}
                self.wfile.write(f"data: {json.dumps(ch)}\n\n".encode())
            u = {"id": "x", "object": "chat.completion.chunk", "created": int(time.time()), "model": "probe", "choices": [],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}
            self.wfile.write(f"data: {json.dumps(u)}\n\ndata: [DONE]\n\n".encode())
        else:
            body = json.dumps({"id": "x", "object": "chat.completion", "created": int(time.time()), "model": "probe",
                               "choices": [{"index": 0, "message": {"role": "assistant", "content": "Done."},
                                            "finish_reason": "stop"}],
                               "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
