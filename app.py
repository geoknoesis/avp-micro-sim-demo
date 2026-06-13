"""AVP-Micro protocol simulator -- interactive Streamlit demo.

Visualises the declarative use cases (engine/sim-scenarios.json) in plain language:
a one-line outcome, a flow diagram of who signs what, the money moving on the
simulated play-money ledger, and a step-by-step story -- with the raw signed JSON
tucked behind expanders. No real money: settlement is a stubbed in-memory ledger.

Run:  streamlit run app.py
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "engine"))
import sim  # noqa: E402  (vendored engine)

st.set_page_config(page_title="AVP-Micro Simulator", page_icon="🔐", layout="wide")

# ---- vocabulary ------------------------------------------------------------

GROUPS = {
    "① One-off payments": [
        "one-off-happy-path", "over-per-transaction-cap", "payee-not-allowed",
        "category-not-allowed", "daily-limit-exceeded", "daily-limit-resets-next-day",
        "authorization-expired", "replayed-authorization",
    ],
    "② Binding & integrity": ["tampered-quote", "amount-mismatch", "currency-mismatch", "corrupted-signature"],
    "③ Settlement outcomes": ["insufficient-funds", "partial-settlement"],
    "④ Human-present approval": ["human-present-confirmed", "human-present-missing", "human-present-forged"],
    "⑤ Streaming / metered": ["streaming-happy", "streaming-budget-exceeded", "streaming-extend-budget"],
    "⑥ AP2 bridge (imported authority)": [
        "bridge-imported-mandate-happy", "bridge-imported-over-cap",
        "bridge-human-present-imported", "bridge-human-present-imported-missing",
    ],
}

ROLE = {  # role -> (colour, icon, what they do)
    "Principal": ("#7c3aed", "👤", "Issues the spending authority; signs fresh human approvals"),
    "Agent": ("#2563eb", "🤖", "Holds the authority; requests quotes and signs authorizations"),
    "Payee": ("#059669", "🏪", "Provides the service; signs quotes, usage, and receipts"),
    "Wallet": ("#d97706", "🏦", "Verifies everything, enforces policy, settles, signs executions"),
    "Ledger": ("#6b7280", "💰", "The (simulated) settlement rail — play money only"),
}

# action -> (sender, receiver, plain verb phrase)
FLOW = {
    "quote": ("Payee", "Agent", "sends a signed price quote"),
    "authorize": ("Agent", "Wallet", "signs an authorization to pay — binds the quote and presents its mandate"),
    "confirm": ("Principal", "Wallet", "signs a fresh human approval of this exact purchase"),
    "execute": ("Wallet", "Ledger", "verifies everything, then settles"),
    "replay": ("Agent", "Wallet", "re-submits the same authorization"),
    "receipt": ("Payee", "Agent", "acknowledges delivery with a signed receipt"),
    "open_session": ("Payee", "Agent", "opens a metered session with a budget cap"),
    "budget_authorize": ("Agent", "Wallet", "commits to a session budget"),
    "accrue": ("Payee", "Wallet", "reports incremental usage"),
    "close_session": ("Wallet", "Ledger", "settles the accrued total"),
}
CONTROL = {  # non-message steps
    "advance_clock": ("⏩", "time passes (testing expiry / daily windows)"),
    "corrupt_authz": ("🧨", "an attacker corrupts the authorization's signature"),
    "tamper_quote": ("🧨", "an attacker alters the quote after it was signed"),
    "extend": ("➕", "the session budget cap is raised"),
}
PRODUCER = {a: v[0] for a, v in FLOW.items()}

# rejection code -> plain explanation
WHY = {
    "overCap": "the amount is above the agent's per-transaction limit",
    "payeeNotAllowed": "this payee isn't on the agent's allow-list",
    "categoryNotAllowed": "this category isn't permitted by the mandate",
    "dailyLimitExceeded": "this would exceed the agent's daily spending limit",
    "expired": "the authorization's validity window has passed",
    "nonceReuse": "this authorization was already used (replay blocked)",
    "doubleSpend": "this authorization was already settled once",
    "quoteMismatch": "the quote was altered after it was signed (digest mismatch)",
    "amountMismatch": "the authorization's amount doesn't match the quote it cites",
    "currencyMismatch": "the currency isn't the one the mandate authorizes",
    "badSignature": "the authorization's signature is invalid",
    "badCredential": "the embedded authority failed verification",
    "holderMismatch": "the signer isn't the subject of the credential",
    "budgetExceeded": "this usage would exceed the committed session budget",
    "missingConfirmation": "fresh human approval is required, but none was provided",
    "forgedConfirmation": "the approval wasn't signed by the principal",
}

SCENARIOS = {s["name"]: s for s in sim.load_scenarios()}


# ---- helpers ----------------------------------------------------------------

def short(did):
    return (did[:22] + "…") if did and len(did) > 24 else did


def chip(outcome) -> str:
    if outcome["outcome"] == "reject":
        return f":red[**⛔ refused — {WHY.get(outcome['code'], outcome['code'])}**]"
    s = outcome.get("status")
    if s == "completed":
        return f":green[**✅ settled {outcome.get('settled')}**]"
    if s == "partial":
        return f":orange[**◑ partially settled {outcome.get('settled')}**]"
    if s == "failed":
        return ":red[**⚠️ settlement failed — no funds**]"
    return ":green[**✅ ok**]"


def scenario_summary(res):
    """(streamlit-fn, one-line plain-English summary)."""
    for rec in res["trace"]:
        if rec["outcome"]["outcome"] == "reject":
            code = rec["outcome"]["code"]
            return st.error, f"**Refused** — {WHY.get(code, code)}. No money moved."
    last = None
    for rec in res["trace"]:
        if rec["action"] in ("execute", "close_session"):
            last = rec["outcome"]
    if last:
        s = last.get("status")
        if s == "completed":
            return st.success, f"**Paid** — the agent paid the payee **{last.get('settled')}** on the simulated ledger."
        if s == "partial":
            return st.warning, f"**Partially settled** — only **{last.get('settled')}** could move."
        if s == "failed":
            return st.warning, "**Settlement failed** — the simulated ledger had no funds."
    return st.success, "Completed."


def flow_dot(res) -> str:
    lines = ['digraph G {', 'rankdir=LR; bgcolor="transparent";',
             'node [shape=box style="rounded,filled" fontname="Helvetica" fontcolor=white fontsize=12 margin="0.18,0.10"];',
             'edge [fontname="Helvetica" fontsize=10];']
    used = {"Ledger"}
    edges = []
    n = 1
    for rec in res["trace"]:
        if rec["action"] not in FLOW:
            continue
        a, b, _ = FLOW[rec["action"]]
        used.add(a); used.add(b)
        ok = rec["outcome"]["outcome"] == "ok" and rec["outcome"].get("status") != "failed"
        colour = "#059669" if ok else "#dc2626"
        label = f'{n}. {rec["action"]}'
        amt = rec["params"].get("amount")
        if amt:
            label += f'  {amt}'
        dash = "" if ok else ' style=dashed'
        edges.append(f'"{a}" -> "{b}" [label="{label}" color="{colour}" fontcolor="{colour}" penwidth=2{dash}];')
        n += 1
    for role in ["Principal", "Agent", "Payee", "Wallet", "Ledger"]:
        if role in used:
            colour, icon, _ = ROLE[role]
            lines.append(f'"{role}" [label="{role}" fillcolor="{colour}"];')
    lines += edges
    lines.append('}')
    return "\n".join(lines)


def money_panel(res):
    start, final = res["start"], res["final"]
    roles = [r for r in ["agent", "payee", "payee2"] if r in start or r in final]
    roles += [r for r in sorted(set(start) | set(final)) if r not in roles]
    cols = st.columns(len(roles) or 1)
    for col, r in zip(cols, roles):
        s, f = Decimal(start.get(r, "0")), Decimal(final.get(r, "0"))
        d = f - s
        col.metric(f"{r} balance", f"{f}", delta=(str(d) if d != 0 else None),
                   delta_color="normal" if d >= 0 else "inverse")


def render_header(res):
    fn, msg = scenario_summary(res)
    fn(msg)
    st.caption(res["description"])
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Message flow** — green = accepted/settled, red dashed = refused")
        st.graphviz_chart(flow_dot(res), use_container_width=True)
    with right:
        st.markdown("**Money on the simulated ledger** (play money — no real funds)")
        money_panel(res)
        with st.expander("Spending policy (the mandate's terms)"):
            st.json(res["policy"])
        kind = "AP2 IntentMandate imported via did:web" if res["imported"] else "principal-signed credential"
        with st.expander(f"🔑 Spending Authorization Credential — {kind}"):
            if res["imported"]:
                st.caption("verified by the wallet against did:web issuers: " + ", ".join(res["resolver"]))
            st.json(res["credential"])


# ---- detail views -----------------------------------------------------------

def render_story(res):
    st.markdown("#### Step by step")
    for rec in res["trace"]:
        action = rec["action"]
        amt = rec["params"].get("amount")
        if action in FLOW:
            a, b, phrase = FLOW[action]
            ia, ib = ROLE[a][1], ROLE[b][1]
            extra = f" **{amt}**" if amt else ""
            st.markdown(f"**{rec['i'] + 1}.** {ia} **{a}** → {ib} **{b}** — {phrase}{extra}  {chip(rec['outcome'])}")
            if rec["object"]:
                with st.expander("signed message (JSON)"):
                    st.json(rec["object"])
        else:
            icon, note = CONTROL.get(action, ("•", action))
            detail = ""
            if action == "advance_clock":
                detail = f" (+{rec['params'].get('seconds', '?')}s)"
            if action == "extend":
                detail = f" → new cap {rec['params'].get('newBudget')}"
            st.markdown(f"**{rec['i'] + 1}.** {icon} _{note}{detail}_")
        st.divider()


def render_participants(res):
    st.markdown("#### Each participant's view")
    dids = {"Principal": res["credential"].get("issuer"), "Agent": None, "Payee": None, "Wallet": None}
    for rec in res["trace"]:
        o = rec["object"] or {}
        dids["Agent"] = o.get("payer", dids["Agent"])
        dids["Payee"] = o.get("payee", dids["Payee"])
        dids["Wallet"] = o.get("wallet", dids["Wallet"])
        if o.get("confirmedBy"):
            dids["Principal"] = o["confirmedBy"]

    cols = st.columns(4)
    for col, role in zip(cols, ["Principal", "Agent", "Payee", "Wallet"]):
        colour, icon, desc = ROLE[role]
        with col:
            st.markdown(f"<h4 style='color:{colour};margin-bottom:0'>{icon} {role}</h4>", unsafe_allow_html=True)
            st.caption(desc)
            if dids.get(role):
                st.code(short(dids[role]), language=None)
            if role == "Principal":
                with st.expander("🔑 authority it issues"):
                    st.json(res["credential"])
            if role == "Agent":
                with st.expander("🔑 authority it holds (in every vp)"):
                    st.json(res["credential"])

            mine = [r for r in res["trace"] if PRODUCER.get(r["action"]) == role]
            if not mine:
                st.caption("_— no messages in this scenario —_")
            for r in mine:
                tag = (" " + chip(r["outcome"])) if role == "Wallet" else ""
                st.markdown(f"**{r['i'] + 1}. {r['action']}**{tag}")
                if r["object"]:
                    with st.expander("signed message"):
                        st.json(r["object"])
                if role == "Wallet":
                    st.caption("ledger → " + json.dumps(r["balances"]))
            if role == "Wallet":
                st.markdown("**ledger end**")
                st.json(res["final"])


def render_overview():
    st.markdown("### All use cases")
    st.caption("Every scenario, run through the engine. ✅ = behaved exactly as declared.")
    for group, names in GROUPS.items():
        st.markdown(f"**{group}**")
        for n in names:
            if n in SCENARIOS:
                res = sim.run_traced(SCENARIOS[n])
                st.markdown(f"- {'✅' if res['ok'] else '❌'} `{n}` — {res['description']}")


# ---- layout -----------------------------------------------------------------

st.title("🔐 AVP-Micro — agent payments, simulated")
st.caption("Real `ecdsa-jcs-2022` signatures and full wallet policy enforcement, settled on a "
           "**play-money ledger**. Settlement is the only money-touching step and is stubbed — "
           "**no real funds move anywhere.**")

st.sidebar.header("Demo")
view = st.sidebar.radio("View", ["Walk a use case", "Overview (all)"])

if view == "Walk a use case":
    group = st.sidebar.selectbox("Category", list(GROUPS.keys()))
    name = st.sidebar.radio("Use case", GROUPS[group])
    res = sim.run_traced(SCENARIOS[name])
    st.subheader(name.replace("-", " "))
    render_header(res)
    st.markdown("---")
    detail = st.radio("Detail view", ["📖 Step by step", "👥 By participant"], horizontal=True)
    (render_story if detail.startswith("📖") else render_participants)(res)
else:
    render_overview()

st.sidebar.divider()
st.sidebar.caption(f"{len(SCENARIOS)} use cases · engine vendored from avp-micro-spec · no real money")
