"""A tiny runnable AVP-Micro payee + wallet HTTP server (stdlib only).

Serves the real HTTP 402 challenge flow with real `ecdsa-jcs-2022` signatures and the
reference wallet's real policy enforcement (via `live.py` / the bundled engine). It is a
demonstration server: the wallet decision is computed from the policy encoded in the query
parameters, and challenge nonces are single-use (a replayed retry is refused 409).

Run:
    python server.py            # serves on http://localhost:8402

Try it:
    curl http://localhost:8402/.well-known/avp-micro
    curl -i "http://localhost:8402/resource/premium?amount=1.00&cap=5.00&payee=allowed"
    curl -i "http://localhost:8402/resource/premium?amount=1.00&cap=5.00&payee=allowed" \
         -H 'Authorization: AVP-Micro retry'         # -> 200 + execution (or 4xx + problem)
    # repeat the authorized call -> 409 nonce-reuse (single-use challenge)
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import live
import avp_crypto as ac  # on path via live.py's sys.path insert

PORT = 8402
_CONSUMED: set[str] = set()  # consumed challenge nonces (single-use; anti-replay)


def _params(qs: dict) -> dict:
    g = lambda k, d=None: qs.get(k, [d])[0]  # noqa: E731
    return {
        "amount": g("amount", "1.00"),
        "maxPerTransaction": g("cap", "5.00"),
        "currency": g("currency", "USD"),
        "payeeAllowed": g("payee", "allowed") != "blocked",
        "requireConfirmation": g("confirm") == "required",
        "provideConfirmation": g("confirm") == "provided",
    }


def _service_description() -> dict:
    sd = {
        "@context": live.TXP_CTX, "id": "urn:avp:txp:service:live", "type": "ServiceDescription",
        "payee": live.PAYEE_DID,
        "endpoints": {"quote": "/quote", "authorize": "/resource/premium",
                      "execute": "/resource/premium", "receipt": "/receipt/{id}",
                      "settlementStatus": "/settlement/{id}"},
        "acceptedSettlementRails": ["https://w3id.org/avp-micro/settlement/v1#rail-evm-stablecoin"],
        "supportedBundles": {live.AVP: "0.1.0", live.TXP_URL: "0.1.0"},
        "timestamp": live._NOW,
    }
    return ac.sign_ecdsa_jcs_2022(sd, live.PAYEE_KEY, live._NOW)


class Handler(BaseHTTPRequestHandler):
    server_version = "AVP-Micro-Live/0.1"

    def _send(self, status: int, body: dict, headers: dict | None = None):
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        if u.path == "/.well-known/avp-micro":
            self._send(200, _service_description(), {"Content-Type": "application/avp-micro+json"})
            return
        if u.path.rstrip("/") == "/resource/premium":
            params = _params(parse_qs(u.query))
            result = live.build_exchange(params)
            steps = result["exchange"]["steps"]
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("AVP-Micro "):
                # first hit: 402 challenge (nonce becomes valid/pending)
                resp = steps[0]["response"]
                _CONSUMED.discard(self._nonce(params))  # fresh challenge issued
                self._send(resp["status"], resp["body"], resp["headers"])
                return
            # authorized retry: enforce single-use challenge
            nonce = self._nonce(params)
            if nonce in _CONSUMED:
                self._send(409, {"type": live.TXP_URL + "#nonce-reuse",
                                 "title": "Nonce reuse", "status": 409,
                                 "detail": "This challenge nonce was already consumed."},
                           {"Content-Type": "application/problem+json",
                            "WWW-Authenticate": 'AVP-Micro error="nonce-reuse"'})
                return
            _CONSUMED.add(nonce)
            resp = steps[1]["response"]
            self._send(resp["status"], resp["body"], resp["headers"])
            return
        self._send(404, {"type": live.TXP_URL + "#malformed-request", "title": "Not found",
                         "status": 404, "detail": f"No such resource: {u.path}"},
                   {"Content-Type": "application/problem+json"})

    @staticmethod
    def _nonce(params: dict) -> str:
        return "live-nonce-" + str(params.get("amount", "1.00")).replace(".", "_")

    def log_message(self, fmt, *args):  # quieter logs
        print("  " + (fmt % args))


def main():
    httpd = ThreadingHTTPServer(("localhost", PORT), Handler)
    print(f"AVP-Micro live payee+wallet server on http://localhost:{PORT}")
    print(f"  payee {live.PAYEE_DID}")
    print("  GET /.well-known/avp-micro  |  GET /resource/premium[?amount=&cap=&payee=allowed|blocked&confirm=required|provided]")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
