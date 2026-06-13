"""AVP-Micro protocol simulator -- interactive Streamlit demo.

Drives the declarative use cases from the vendored simulator engine (engine/sim.py)
and visualises each one: the spending-authority credential, the step-by-step signed
message flow with wallet decisions, and the simulated play-money ledger. No real
money is involved anywhere -- settlement is a stubbed in-memory ledger.

Run:  streamlit run app.py
"""
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "engine"))
import sim  # noqa: E402  (vendored engine)

st.set_page_config(page_title="AVP-Micro Simulator", page_icon="🔐", layout="wide")

# ---- scenario grouping (for the sidebar) -----------------------------------

GROUPS = {
    "One-off payments": [
        "one-off-happy-path", "over-per-transaction-cap", "payee-not-allowed",
        "category-not-allowed", "daily-limit-exceeded", "daily-limit-resets-next-day",
        "authorization-expired", "replayed-authorization",
    ],
    "Binding & integrity": [
        "tampered-quote", "amount-mismatch", "currency-mismatch", "corrupted-signature",
    ],
    "Settlement outcomes": ["insufficient-funds", "partial-settlement"],
    "Human-present approval": [
        "human-present-confirmed", "human-present-missing", "human-present-forged",
    ],
    "Streaming / metered": [
        "streaming-happy", "streaming-budget-exceeded", "streaming-extend-budget",
    ],
    "AP2 bridge (imported authority)": [
        "bridge-imported-mandate-happy", "bridge-imported-over-cap",
        "bridge-human-present-imported", "bridge-human-present-imported-missing",
    ],
}

# action -> (icon, who acts, one-line meaning)
ACTIONS = {
    "quote": ("🧾", "payee → agent", "payee signs a priced PaymentQuote bound to the request"),
    "authorize": ("✍️", "agent → wallet", "agent signs a PaymentAuthorization (embeds the credential, binds the quote)"),
    "confirm": ("🙋", "principal → wallet", "principal signs a fresh PurchaseConfirmation (human-present)"),
    "execute": ("🏦", "wallet → ledger", "wallet verifies everything, settles on the simulated rail, signs a PaymentExecution"),
    "replay": ("🔁", "agent → wallet", "the same authorization is presented again"),
    "receipt": ("📩", "payee → agent", "payee signs a PaymentReceipt for the delivery"),
    "advance_clock": ("⏩", "—", "time passes (tests expiry / daily windows)"),
    "corrupt_authz": ("🧨", "attacker", "the authorization's proof bytes are corrupted"),
    "tamper_quote": ("🧨", "attacker", "the quote is mutated after the authorization committed its digest"),
    "open_session": ("📡", "payee → agent", "payee opens a metered UsageSession with a budget cap"),
    "budget_authorize": ("✍️", "agent → wallet", "agent commits to a session budget (SessionBudgetAuthorization)"),
    "accrue": ("📈", "payee → wallet", "payee reports incremental usage (UsageAccrual)"),
    "extend": ("➕", "payee → agent", "the session budget cap is raised (UsageSessionExtension)"),
    "close_session": ("🏦", "wallet → ledger", "wallet settles the accrued total and signs the execution"),
}

SCENARIOS = {s["name"]: s for s in sim.load_scenarios()}

# which participant signs (produces) each message
PRODUCER = {
    "quote": "Payee", "authorize": "Agent", "confirm": "Principal", "execute": "Wallet",
    "replay": "Agent", "receipt": "Payee", "open_session": "Payee",
    "budget_authorize": "Agent", "accrue": "Payee", "close_session": "Wallet",
}
# the four participant "wallets", in flow order
PARTICIPANTS = [
    ("Principal", "👤", "Issues the spending authority; signs fresh human approvals"),
    ("Agent", "🤖", "Holds the authority; requests quotes and signs authorizations"),
    ("Payee", "🏪", "Provides the service; signs quotes, usage, and receipts"),
    ("Wallet", "🏦", "Verifies everything, enforces policy, settles, signs executions"),
]


def short(did):
    return (did[:20] + "…") if did and len(did) > 22 else did


def outcome_badge(outcome: dict) -> str:
    if outcome["outcome"] == "reject":
        return f":red[⛔ rejected — `{outcome['code']}`]"
    if "status" in outcome:
        colour = {"completed": "green", "partial": "orange", "failed": "red"}.get(outcome["status"], "blue")
        settled = outcome.get("settled")
        return f":{colour}[✅ {outcome['status']}" + (f" — settled {settled}]" if settled is not None else "]")
    return ":green[✅ ok]"


def render_scenario(name: str):
    sc = SCENARIOS[name]
    res = sim.run_traced(sc)

    st.subheader(name)
    st.write(res["description"])
    if res["ok"]:
        st.success("Scenario behaved exactly as specified ✅")
    else:
        st.error("Scenario did NOT match its declared expectations ❌")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Spending policy** (the credential terms)")
        st.json(res["policy"])
    with c2:
        st.markdown("**Ledger — start** (play money)")
        st.json(res["start"])
    with c3:
        st.markdown("**Ledger — end**")
        st.json(res["final"])
        if res["finalBalances"]:
            st.caption("expected: " + json.dumps(res["finalBalances"]))

    label = ("AP2-imported authority (bridge): a foreign IntentMandate verified via did:web"
             if res["imported"] else "Native authority: a principal-signed credential")
    with st.expander(f"🔑 Spending Authorization Credential — {label}"):
        if res["imported"]:
            st.caption("did:web issuers resolved by the wallet: " + ", ".join(res["resolver"]))
        st.json(res["credential"])

    st.markdown("#### Message flow")
    for rec in res["trace"]:
        icon, who, meaning = ACTIONS.get(rec["action"], ("•", "", ""))
        params = {k: v for k, v in rec["params"].items() if k not in ("request",)}
        ptxt = "  ".join(f"`{k}={v}`" for k, v in params.items()) if params else ""
        head = f"{icon} **{rec['i']}. {rec['action']}**  ·  {who}  {ptxt}"
        mark = "" if rec["matched"] else "  :red[(unexpected)]"
        st.markdown(f"{head} — {outcome_badge(rec['outcome'])}{mark}")
        st.caption(meaning)
        if rec["object"]:
            with st.expander("signed message"):
                st.json(rec["object"])
        st.divider()


def render_participants(name: str):
    """One panel per participant 'wallet': the messages it signs/holds, and (for the
    wallet/verifier) its decision and the play-money ledger after each settlement."""
    sc = SCENARIOS[name]
    res = sim.run_traced(sc)

    st.subheader(name)
    st.write(res["description"])
    (st.success if res["ok"] else st.error)(
        "Behaved as specified ✅" if res["ok"] else "Did NOT match expectations ❌")

    # derive each participant's DID from the signed messages
    dids = {"Principal": res["credential"].get("issuer"), "Agent": None, "Payee": None, "Wallet": None}
    for rec in res["trace"]:
        o = rec["object"] or {}
        if "payer" in o:
            dids["Agent"] = o["payer"]
        if "payee" in o:
            dids["Payee"] = o["payee"]
        if o.get("wallet"):
            dids["Wallet"] = o["wallet"]
        if o.get("confirmedBy"):
            dids["Principal"] = o["confirmedBy"]

    st.markdown("#### Participants")
    cols = st.columns(4)
    for col, (role, icon, desc) in zip(cols, PARTICIPANTS):
        with col:
            st.markdown(f"### {icon} {role}")
            st.caption(desc)
            if dids.get(role):
                st.code(short(dids[role]), language=None)

            if role == "Principal":
                kind = "AP2 IntentMandate, imported via did:web" if res["imported"] else "principal-signed credential"
                with st.expander(f"🔑 authority issued ({kind})"):
                    st.json(res["credential"])
            if role == "Agent":
                with st.expander("🔑 authority held (presented in every authorization's vp)"):
                    st.json(res["credential"])

            produced = [r for r in res["trace"] if PRODUCER.get(r["action"]) == role]
            if not produced and role not in ("Principal", "Agent"):
                st.caption("_(no messages in this scenario)_")
            for r in produced:
                badge = (" — " + outcome_badge(r["outcome"])) if role == "Wallet" else ""
                st.markdown(f"**{r['i']}. `{r['action']}`**{badge}")
                if r["object"]:
                    with st.expander("signed message"):
                        st.json(r["object"])
                if role == "Wallet":
                    st.caption("ledger after → " + json.dumps(r["balances"]))

            if role == "Wallet":
                st.markdown("**Settlement ledger** (play money)")
                cc = st.columns(2)
                cc[0].caption("start"); cc[0].json(res["start"])
                cc[1].caption("end"); cc[1].json(res["final"])
            if role == "Payee" and dids.get("Payee"):
                # the payee's role name on the ledger is the settlementTarget suffix; show received
                pass


def render_overview():
    st.subheader("All use cases")
    st.caption("Every scenario, run through the engine. Green = behaved as declared.")
    for group, names in GROUPS.items():
        st.markdown(f"**{group}**")
        for n in names:
            if n not in SCENARIOS:
                continue
            res = sim.run_traced(SCENARIOS[n])
            mark = "✅" if res["ok"] else "❌"
            st.markdown(f"- {mark} `{n}` — {res['description']}")


# ---- layout -----------------------------------------------------------------

st.title("🔐 AVP-Micro — protocol simulator")
st.caption("Agent payments end to end with real `ecdsa-jcs-2022` signatures and full "
           "wallet-side policy enforcement, against a **simulated play-money ledger**. "
           "Settlement is the only money-touching step and is stubbed — no real funds move.")

st.sidebar.header("Use cases")
view = st.sidebar.radio("View", ["Single scenario", "Overview (all)"])
if view == "Single scenario":
    group = st.sidebar.selectbox("Category", list(GROUPS.keys()))
    name = st.sidebar.radio("Scenario", GROUPS[group])
    layout = st.radio("Layout", ["Participant wallets", "Message flow (timeline)"], horizontal=True)
    if layout == "Participant wallets":
        render_participants(name)
    else:
        render_scenario(name)
else:
    render_overview()

st.sidebar.divider()
st.sidebar.caption(f"{len(SCENARIOS)} declarative use cases · engine: vendored from avp-micro-spec")
