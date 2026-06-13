# AVP-Micro protocol simulator — interactive demo

A [Streamlit](https://streamlit.io) app that demonstrates the **AVP-Micro** agent-payment
protocol end to end — quote → authorize → execute → receipt, plus streaming/metered
sessions (including **pay-per-token** LLM streaming), human-present approval, authority
imported across the **AP2 bridge**, and the **refund / reversal / dispute** lifecycle —
across **32 declarative use cases**, with **no real money**.

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

Then pick a use case in the sidebar. For each one the app shows:

- the **Spending Authorization Credential** (native, or an AP2-imported projection verified via `did:web`);
- the **step-by-step signed message flow** — who acts, the wallet's decision, and the signed JSON each step emits;
- the **play-money ledger** before and after; and
- whether the run matched the scenario's declared expectation.

## The use cases

Defined declaratively in [`engine/sim-scenarios.json`](engine/sim-scenarios.json):

| Group | Scenarios |
|---|---|
| ① One-off payments | happy path · over-cap · payee-not-allowed · category-not-allowed · daily-limit exceeded / resets next day · expired · replayed |
| ② Binding & integrity | tampered-quote · amount-mismatch · currency-mismatch · corrupted-signature |
| ③ Settlement outcomes | insufficient-funds (`failed`) · partial-settlement (`partial`) |
| ④ Human-present approval | confirmed · missing · forged (signer ≠ `confirmedBy`) |
| ⑤ Streaming / metered | **pay-per-token** LLM streaming · metered session · happy · budget-exceeded · extend-budget mid-session |
| ⑥ AP2 bridge (imported authority) | imported-mandate happy · imported over-cap · human-present via imported confirmation · missing |
| ⑦ Refunds, reversals & disputes | refund full / partial · over-refund rejected · dispute upheld → chargeback · dispute rejected · withdrawn |

Streaming use cases show a **live budget gauge** (cost and token count climbing toward the cap);
dispute use cases add an **⚖️ Arbiter** participant.

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
