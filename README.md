# AVP-Micro protocol simulator — interactive demo

A [Streamlit](https://streamlit.io) app that demonstrates the **AVP-Micro** agent-payment
protocol end to end — credential issuance/delegation, quote → authorize → execute → receipt,
plus streaming/metered sessions (including **pay-per-token** LLM streaming), human-present
approval, authority imported across the **AP2 bridge**, and the **refund / reversal / dispute**
lifecycle — across **37 declarative use cases**, with **no real money**.

Every message is signed for real with `ecdsa-jcs-2022` (P-256) and verified by a wallet
that enforces the full policy (spend caps, allowed payees/categories, daily limits,
quote/`requestHash` binding, nonce/replay, single-use consumption, session budgets, and
fresh human approval). The **only** money-touching step — settlement — is the one part the
specification scopes out, so it is stubbed by an in-memory ledger of play balances. No real
funds move anywhere.

## Run it

```bash
python -m venv .venv && . .venv/bin/activate      # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
streamlit run app.py
```

The header shows the four-box mental model (**Principal → Agent → Wallet → Payee**) and the
sidebar carries a colour-coded **cast** legend so every diagram stays readable. Three views:

- **Walk a use case** — one scenario end to end: a plain-English **outcome banner** (with the
  machine refusal code when refused), the **message-flow diagram**, the **play-money ledger**
  before/after (and a live **session-budget gauge** for streaming), then tabs for the
  **📖 walkthrough**, **👥 by-participant** view, **🔑 policy & authority** (the mandate's terms
  and the Spending Authorization Credential — native, or an AP2-imported projection verified via
  `did:web`), and the **🧩 declarative source** (the exact JSON that defines the use case).
- **All use cases** — every scenario at a glance with a pass/fail badge; press **Walk →** on any
  row to jump straight into it.
- **Conformance vectors** — see below.

## The use cases

Defined declaratively in [`engine/sim-scenarios.json`](engine/sim-scenarios.json):

| Group | Scenarios |
|---|---|
| ⓪ Delegate authority (issuance) | principal issues a bounded credential to the agent · issued to the wrong key → holder-mismatch · issued already-expired · issued then revoked · **AP2**: the user issues an IntentMandate the agent imports |
| ① One-off payments | happy path · over-cap · payee-not-allowed · category-not-allowed · daily-limit exceeded / resets next day · expired · replayed |
| ② Binding & integrity | tampered-quote · amount-mismatch · currency-mismatch · corrupted-signature |
| ③ Settlement outcomes | insufficient-funds (`failed`) · partial-settlement (`partial`) |
| ④ Human-present approval | confirmed · missing · forged (signer ≠ `confirmedBy`) |
| ⑤ Streaming / metered | **pay-per-token** LLM streaming · metered session · happy · budget-exceeded · extend-budget mid-session |
| ⑥ AP2 bridge (imported authority) | imported-mandate happy · imported over-cap · human-present via imported confirmation · missing |
| ⑦ Refunds, reversals & disputes | refund full / partial · over-refund rejected · dispute upheld → chargeback · dispute rejected · withdrawn |

Streaming use cases show a **live budget gauge** (cost and token count climbing toward the cap);
dispute use cases add an **⚖️ Arbiter** participant.

## Conformance test vectors

A third sidebar view, **Conformance vectors**, lists *every* signed conformance test
vector from the spec — Authority, Payments, Interop, and Disputes (~50 of them) — each as a
use case, with its `ecdsa-jcs-2022` proof verified and the signed JSON inspectable. These are
read **live** from a sibling `avp-micro-spec` checkout (or `AVP_SPEC_DIR`), so they stay current;
if the spec repo isn't found, this view degrades gracefully and the simulator use cases still work.

## Engine

The simulator engine under [`engine/`](engine/) is vendored from the
[`avp-micro-spec`](https://github.com/geoknoesis/avp-micro-spec) repository
(`spec/sim.py`, `spec/sim-scenarios.json`, and the `ecdsa-jcs-2022` / SD-JWT-VC crypto
modules). It depends only on `cryptography`. To run the same scenarios headless:

```bash
python engine/sim.py            # PASS/FAIL per scenario
```

> This is a demonstration/teaching tool. Settlement is simulated; to exercise a real rail
> without real money, point the engine's `SettlementRail` at a testnet or sandbox.
