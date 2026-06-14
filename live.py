"""Live AVP-Micro 402 exchange — real signatures, real wallet policy.

Drives the bundled reference engine (`sim.py`) from a small set of parameters and produces
a *real* HTTP 402 exchange: a payee-signed `PaymentChallenge` wrapping a freshly signed
`PaymentQuote`, the agent-signed `AuthorizationSubmission`, and the wallet's actual verdict
(a `PaymentExecution` on success, or a `ProblemDetails` with the spec error code on refusal).

Nothing is mocked: the quote/authorization/execution are signed with `ecdsa-jcs-2022` and
the accept/reject decision is the reference wallet's real policy enforcement. The transport
wrapper objects are signed with the same deterministic keys the engine uses for the payee
and agent (`ac.seed_key("sim:payee")` / `"sim:agent"`), so every digest binds.

Used by the demo's "Live (try it)" view and by `server.py` (a runnable localhost server).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "engine"))
import sim  # noqa: E402
import avp_crypto as ac  # noqa: E402

VC2 = "https://www.w3.org/ns/credentials/v2"
DI = "https://w3id.org/security/data-integrity/v2"
DSA = "https://w3id.org/spending-authority/v1"
AVP = "https://w3id.org/avp-micro/v1"
TXP_URL = "https://w3id.org/avp-micro/transport/v1"
TXP_CTX = [VC2, DI, DSA, AVP, TXP_URL]

# the engine's deterministic payee/agent keys (Actor("payee") / Actor("agent"))
PAYEE_KEY = ac.seed_key("sim:payee")
AGENT_KEY = ac.seed_key("sim:agent")
PAYEE_DID = ac.did_key(PAYEE_KEY.public_key())
AGENT_DID = ac.did_key(AGENT_KEY.public_key())

JCT = {"Content-Type": "application/avp-micro+json"}
PCT = {"Content-Type": "application/problem+json"}

# reference reject code -> (transport error-code local name, HTTP status)  [transport §4.7]
_REJECT_MAP = {
    "overCap": ("over-cap", 402),
    "dailyLimitExceeded": ("daily-limit-exceeded", 402),
    "budgetExceeded": ("budget-exceeded", 402),
    "payeeNotAllowed": ("payee-not-allowed", 403),
    "categoryNotAllowed": ("category-not-allowed", 403),
    "missingConfirmation": ("missing-confirmation", 403),
    "credentialRevoked": ("credential-revoked", 403),
    "badSignature": ("unauthorized", 401),
    "badCredential": ("unauthorized", 401),
    "holderMismatch": ("unauthorized", 401),
    "credentialExpired": ("unauthorized", 401),
    "nonceReuse": ("nonce-reuse", 409),
    "doubleSpend": ("double-spend", 409),
    "amountMismatch": ("amount-mismatch", 422),
    "currencyMismatch": ("currency-mismatch", 422),
    "quoteMismatch": ("amount-mismatch", 422),
    "expired": ("expired", 422),
    "forgedConfirmation": ("forged-confirmation", 422),
}
_NOW = "2026-06-12T10:00:00Z"
_EXPIRES = "2026-06-12T10:05:00Z"


def scenario_from_params(params: dict) -> dict:
    """Build a one-off scenario from UI parameters (no `expect` — we read the real outcome)."""
    amount = params.get("amount", "1.00")
    cap = params.get("maxPerTransaction", "5.00")
    currency = params.get("currency", "USD")
    policy = {
        "currency": currency,
        "maxPerTransaction": cap,
        "allowedPayees": ["payee"] if params.get("payeeAllowed", True) else ["other"],
    }
    if params.get("dailyLimit"):
        policy["dailyLimit"] = params["dailyLimit"]
    if params.get("requireConfirmation"):
        policy["requiresConfirmation"] = True
    steps = [{"action": "quote", "amount": amount}, {"action": "authorize"}]
    if params.get("requireConfirmation") and params.get("provideConfirmation"):
        steps.append({"action": "confirm"})
    steps.append({"action": "execute"})
    return {
        "name": "live", "description": "Live interactive 402 exchange.",
        "policy": policy, "balances": {"agent": "100.00"}, "now": _NOW, "steps": steps,
    }


def _obj(trace, action, ok_only=False):
    for r in trace:
        if r["action"] == action and (not ok_only or r["outcome"]["outcome"] == "ok"):
            return r.get("object")
    return None


def build_challenge(quote: dict, nonce: str) -> dict:
    ch = {
        "@context": TXP_CTX, "id": "urn:avp:txp:challenge:live", "type": "PaymentChallenge",
        "payee": PAYEE_DID, "quote": quote["id"], "quoteDigest": ac.jcs_digest(quote),
        "challenge": nonce, "authorizeEndpoint": "/resource/premium",
        "timestamp": _NOW, "expires": _EXPIRES,
    }
    return ac.sign_ecdsa_jcs_2022(ch, PAYEE_KEY, _NOW)


def build_submission(authz: dict, nonce: str) -> dict:
    sub = {
        "@context": TXP_CTX, "id": "urn:avp:txp:submission:live", "type": "AuthorizationSubmission",
        "payer": AGENT_DID, "authorization": authz["id"], "authorizationDigest": ac.jcs_digest(authz),
        "challenge": nonce, "idempotencyKey": "live-key",
        "timestamp": _NOW,
    }
    return ac.sign_ecdsa_jcs_2022(sub, AGENT_KEY, _NOW)


def verdict_response(decisive: dict, execution: dict | None) -> dict:
    """Map the engine's decisive outcome to the HTTP response (200 + execution, or 4xx + problem)."""
    if decisive.get("outcome") == "reject":
        code, status = _REJECT_MAP.get(decisive.get("code"), ("malformed-request", 400))
        body = {
            "type": TXP_URL + "#" + code,
            "title": code.replace("-", " ").capitalize(),
            "status": status,
            "detail": f"The wallet refused the charge: {decisive.get('code')}.",
        }
        return {"status": status, "headers": {**PCT, "WWW-Authenticate": f'AVP-Micro error="{code}"'},
                "body": body}
    return {"status": 200, "headers": JCT, "body": execution}


def build_exchange(params: dict) -> dict:
    """Run a real exchange for `params`; return {exchange, verdict}. Never raises."""
    res = sim.run_traced(scenario_from_params(params))
    trace = res["trace"]
    quote = _obj(trace, "quote")
    authz = _obj(trace, "authorize")
    execution = _obj(trace, "execute", ok_only=True)
    decisive = trace[-1]["outcome"] if trace else {"outcome": "ok"}
    nonce = "live-nonce-" + str(params.get("amount", "1.00")).replace(".", "_")
    challenge = build_challenge(quote, nonce)
    submission = build_submission(authz, nonce)
    body_402 = {"challenge": challenge, "quote": quote}
    resp = verdict_response(decisive, execution)
    exchange = {
        "description": "Live HTTP 402 exchange — real ecdsa-jcs-2022 signatures, real wallet policy.",
        "steps": [
            {"request": {"method": "GET", "path": "/resource/premium",
                         "headers": {"Accept": "application/avp-micro+json"}},
             "response": {"status": 402,
                          "headers": {"WWW-Authenticate": f'AVP-Micro challenge="{nonce}"',
                                      "Content-Type": "application/avp-micro+json"},
                          "body": body_402}},
            {"request": {"method": "GET", "path": "/resource/premium",
                         "headers": {"Authorization": "AVP-Micro " + submission["id"],
                                     "Idempotency-Key": "live-key",
                                     "Content-Type": "application/avp-micro+json"},
                         "body": submission},
             "response": resp},
        ],
    }
    return {"exchange": exchange, "verdict": decisive,
            "service": {"payee": PAYEE_DID, "agent": AGENT_DID}}
