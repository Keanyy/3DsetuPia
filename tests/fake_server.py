"""Local HTTP server that imitates OpenAI-compatible and Anthropic endpoints."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ANSWER = {"summary": "Test özeti", "changes": [
    {"key": "wall_loops", "value": "4", "reason": "Daha sağlam."},
    {"key": "machine_start_gcode", "value": "G28", "reason": "kötü"},
    {"key": "layer_height", "value": "0.12", "reason": "İnce detay."}]}


class State:
    def __init__(self):
        self.requests = []
        self.reject_json_mode = False
        self.status = 200


def make_handler(state):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("request-id", "req_test")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            state.requests.append(("GET", self.path, dict(self.headers), None))
            if state.status != 200:
                return self._send(state.status, {"error": {"type": "authentication_error", "message": "bad key"}})
            if self.path.startswith("/v1/models") and "anthropic-version" in self.headers:
                return self._send(200, {"data": [{"id": "claude-opus-5-5", "type": "model",
                                                  "display_name": "Claude Opus 5.5",
                                                  "created_at": "2026-01-01T00:00:00Z"}],
                                        "has_more": False, "first_id": "claude-opus-5-5",
                                        "last_id": "claude-opus-5-5"})
            if self.path.endswith("/models"):
                return self._send(200, {"data": [{"id": "model-b"}, {"id": "model-a"}]})
            self._send(404, {"error": "nf"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            state.requests.append(("POST", self.path, dict(self.headers), body))
            if state.status != 200:
                return self._send(state.status, {"error": {"type": "authentication_error", "message": "bad key"}})
            if self.path.startswith("/v1/messages"):
                return self._send(200, {"id": "msg_1", "type": "message", "role": "assistant",
                                        "model": body.get("model"),
                                        "content": [{"type": "text", "text": json.dumps(ANSWER)}],
                                        "stop_reason": "end_turn", "stop_sequence": None,
                                        "usage": {"input_tokens": 10, "output_tokens": 10}})
            if self.path.endswith("/chat/completions"):
                if state.reject_json_mode and "response_format" in body:
                    return self._send(400, {"error": "response_format not supported"})
                return self._send(200, {"choices": [{"message": {"role": "assistant",
                                                                 "content": json.dumps(ANSWER)}}]})
            self._send(404, {"error": "nf"})
    return H


def start():
    state = State()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, state, "http://127.0.0.1:%d" % srv.server_address[1]
