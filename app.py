"""AVP-Micro protocol simulator -- interactive Streamlit demo.

Walks the declarative use cases (engine/sim-scenarios.json) in plain language so a
developer can see the protocol end to end: who signs what, the policy the wallet
enforces, the money moving on the simulated play-money ledger, and the raw signed
JSON behind every step. No real money: settlement is a stubbed in-memory ledger.

Run:  streamlit run app.py
"""
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "engine"))
import sim  # noqa: E402  (vendored engine)
import avp_crypto as ac  # noqa: E402  (vendored: ecdsa-jcs-2022 verify)

# Locate the spec repo (for the signed conformance test vectors). Read live so the
# list stays current with the spec; degrade gracefully if it isn't a sibling.
SPEC_DIR = next((Path(p) for p in [
    os.environ.get("AVP_SPEC_DIR", ""),
    str(Path(__file__).parent.parent / "avp-micro-spec" / "spec"),
    str(Path(__file__).parent / "spec"),
] if p and Path(p).exists()), None)

BUNDLES = [
    ("Authority (DSA)", "authority"), ("Payments", "payments"),
    ("Interop (SD-JWT-VC)", "interop-sd-jwt-vc"), ("Refunds, reversals & disputes", "disputes"),
    ("On-chain settlement binding", "settlement"),
]

st.set_page_config(page_title="AVP-Micro Simulator", page_icon="🔐", layout="wide")

# ---- look & feel ------------------------------------------------------------
# Authoritative "specification" aesthetic: warm paper, ink text, an editorial
# serif (Fraunces) for headings, IBM Plex for body + cryptographic identifiers,
# a single violet accent for the root of authority. Semantic role colours (below)
# stay as-is because they carry meaning in the diagrams.
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,500&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root{
  --ink:#221c33; --muted:#6c6580; --paper:#faf7f2; --panel:#fffdf9;
  --line:#e8e1d4; --accent:#6d28d9; --accent-soft:#efe9fb; --accent-line:#e3d8fb;
}

.stApp{ background:var(--paper); }
body{ font-family:'IBM Plex Sans',system-ui,-apple-system,sans-serif; color:var(--ink); }
body, [data-testid="stMarkdownContainer"], p, li, label, span{ color:var(--ink); }
button, input, select, textarea{ font-family:inherit; }
h1,h2,h3,h4,h5{ font-family:'Fraunces',Georgia,serif !important; letter-spacing:-.015em; color:var(--ink); }
h1{ font-weight:700; } h2,h3{ font-weight:600; }
code, pre, kbd, samp,
[data-testid="stJson"], [data-testid="stCode"], .stCodeBlock{ font-family:'IBM Plex Mono',ui-monospace,monospace !important; }
a, a:visited{ color:var(--accent); }

/* bordered containers -> cards */
[data-testid="stVerticalBlockBorderWrapper"]{
  border-radius:14px !important; border-color:var(--line) !important;
  background:var(--panel); box-shadow:0 1px 2px rgba(34,28,51,.05);
}
[data-testid="stSidebar"]{ background:#f4efe6; border-right:1px solid var(--line); }
[data-testid="stHeader"]{ background:transparent; }

/* hero */
.avp-hero{ padding:.1rem 0 .2rem; }
.avp-hero .kicker{ font-family:'IBM Plex Mono',monospace; font-size:.72rem; letter-spacing:.18em;
  color:var(--accent); font-weight:600; }
.avp-hero h1{ font-size:2.5rem; margin:.15rem 0 .25rem; line-height:1.04; }
.avp-hero h1 em{ font-style:italic; color:var(--accent); }
.avp-hero .sub{ color:var(--muted); max-width:64ch; font-size:1.02rem; margin:.1rem 0 .95rem; }
.avp-hero .sub code{ background:var(--accent-soft); padding:.04rem .32rem; border-radius:5px; color:var(--accent); }

/* mental-model strip */
.avp-flowmap{ display:flex; align-items:center; gap:.35rem; flex-wrap:wrap; }
.avp-node{ background:var(--panel); border:1px solid var(--line); border-top:3px solid var(--c);
  border-radius:12px; padding:.55rem .85rem; min-width:104px; text-align:center; }
.avp-node .ic{ font-size:1.25rem; line-height:1; }
.avp-node .nm{ font-weight:600; font-size:.92rem; margin-top:.18rem; }
.avp-arrow{ display:flex; flex-direction:column; align-items:center; min-width:88px; flex:1 1 64px; }
.avp-arrow .ln{ color:var(--accent); font-size:1.15rem; line-height:1; }
.avp-arrow .vb{ color:var(--muted); font-size:.7rem; text-align:center; margin-top:.12rem; }

.avp-lead{ color:var(--muted); font-size:1.04rem; margin:.1rem 0 .7rem; max-width:74ch; }
.avp-muted{ color:var(--muted); }

/* category pill */
.avp-pill{ display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:.72rem; font-weight:600;
  color:var(--accent); background:var(--accent-soft); border:1px solid var(--accent-line);
  border-radius:999px; padding:.12rem .58rem; }

/* outcome banner */
.avp-outcome{ display:flex; gap:.85rem; align-items:flex-start; border:1px solid var(--line);
  border-left:5px solid var(--c); background:var(--panel); border-radius:13px; padding:.9rem 1.05rem; }
.avp-outcome .em{ font-size:1.7rem; line-height:1; }
.avp-outcome .ti{ font-weight:700; font-size:1.12rem; color:var(--ink); font-family:'Fraunces',serif; }
.avp-outcome .su{ color:var(--muted); margin-top:.12rem; }
.avp-outcome .mc{ font-family:'IBM Plex Mono',monospace; font-size:.72rem; background:#fdecec; color:#b42318;
  border:1px solid #f6cccc; border-radius:6px; padding:.06rem .38rem; margin-top:.4rem; display:inline-block; }

/* cast legend */
.avp-cast{ display:flex; flex-direction:column; gap:.34rem; }
.avp-cast-row{ display:flex; align-items:center; gap:.42rem; font-size:.84rem; }
.avp-cast-row .dot{ width:9px; height:9px; border-radius:50%; flex:0 0 auto; }
.avp-cast-row .ds{ color:var(--muted); font-size:.75rem; }
</style>
"""

# ---- vocabulary ------------------------------------------------------------

GROUPS = {
    "⓪ Delegate authority (issuance)": [
        "issue-delegate-authority", "issue-wrong-subject", "issue-expired-credential",
        "issue-then-revoked", "issue-ap2-intent",
    ],
    "① One-off payments": [
        "one-off-happy-path", "over-per-transaction-cap", "payee-not-allowed",
        "category-not-allowed", "daily-limit-exceeded", "daily-limit-resets-next-day",
        "authorization-expired", "replayed-authorization",
    ],
    "② Binding & integrity": ["tampered-quote", "amount-mismatch", "currency-mismatch", "corrupted-signature"],
    "③ Settlement outcomes": ["insufficient-funds", "partial-settlement"],
    "④ Human-present approval": ["human-present-confirmed", "human-present-missing", "human-present-forged"],
    "⑤ Streaming / metered": ["streaming-token-usage", "streaming-metered-session", "streaming-happy", "streaming-budget-exceeded", "streaming-extend-budget"],
    "⑥ AP2 bridge (imported authority)": [
        "bridge-imported-mandate-happy", "bridge-imported-over-cap",
        "bridge-human-present-imported", "bridge-human-present-imported-missing",
    ],
    "⑦ Refunds, reversals & disputes": [
        "refund-full", "refund-partial", "over-refund-rejected",
        "dispute-upheld-chargeback", "dispute-rejected", "dispute-withdrawn",
    ],
    "⑧ On-chain settlement binding": [
        "settle-evm-direct", "settle-x402-account-binding", "settle-account-redirection",
        "settle-not-final", "settle-amount-mismatch", "settle-lightning-escrow",
        "settle-evm-escrow-timeout", "settle-reverse",
    ],
}

ROLE = {  # role -> (colour, icon, what they do)
    "Principal": ("#7c3aed", "👤", "Issues the spending authority; signs fresh human approvals"),
    "Agent": ("#2563eb", "🤖", "Holds the authority; requests quotes and signs authorizations"),
    "Payee": ("#059669", "🏪", "Provides the service; signs quotes, usage, and receipts"),
    "Wallet": ("#d97706", "🏦", "Verifies everything, enforces policy, settles, signs executions"),
    "Arbiter": ("#db2777", "⚖️", "Adjudicates a dispute when the parties don't agree"),
    "Ledger": ("#6b7280", "💰", "The (simulated) settlement rail — play money only"),
}
ROLE_SHORT = {
    "Principal": "issues the authority", "Agent": "spends within the rules",
    "Payee": "provides the service", "Wallet": "verifies & settles",
    "Arbiter": "adjudicates disputes", "Ledger": "play-money rail",
}

# the four-box mental model shown in the hero: who hands authority/value to whom
MENTAL_MODEL = [
    ("Principal", "👤", "#7c3aed", "delegates bounded authority"),
    ("Agent", "🤖", "#2563eb", "authorizes each payment"),
    ("Wallet", "🏦", "#d97706", "verifies & settles"),
    ("Payee", "🏪", "#059669", ""),
]

# action -> (sender, receiver, plain verb phrase)
FLOW = {
    "issue": ("Principal", "Agent", "issues a Spending Authorization Credential — delegating bounded authority"),
    "revoke": ("Principal", "Wallet", "revokes the credential — later charges under it are refused"),
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
    "refund": ("Payee", "Agent", "issues a refund — money moves back"),
    "reversal": ("Wallet", "Ledger", "reverses the settlement on the rail"),
    "reversal_ack": ("Agent", "Payee", "acknowledges the reversal"),
    "dispute": ("Agent", "Payee", "raises a dispute over the charge"),
    "dispute_evidence": ("Payee", "Arbiter", "submits evidence"),
    "dispute_resolution": ("Payee", "Agent", "decides the dispute outcome"),
    "payee_binding": ("Payee", "Wallet", "signs a PayeeAccountBinding — proves it controls the on-chain account"),
    "settle_instruct": ("Wallet", "Ledger", "issues a SettlementInstruction — binds the authorization to a concrete rail"),
    "settle_proof": ("Ledger", "Wallet", "returns a SettlementProof — chain transaction + finality"),
    "escrow_lock": ("Wallet", "Ledger", "locks the funds in escrow (hold)"),
    "escrow_release": ("Ledger", "Payee", "releases the escrow to the payee"),
    "escrow_refund": ("Ledger", "Agent", "refunds the escrow to the payer on timeout"),
    "reverse_settle_instruct": ("Wallet", "Ledger", "issues a reverse SettlementInstruction (payer/payee swapped)"),
    "reverse_settle_proof": ("Ledger", "Wallet", "returns the reverse SettlementProof — compensating transfer"),
}
CONTROL = {  # non-message steps
    "advance_clock": ("⏩", "time passes (testing expiry / daily windows)"),
    "corrupt_authz": ("🧨", "an attacker corrupts the authorization's signature"),
    "tamper_quote": ("🧨", "an attacker alters the quote after it was signed"),
    "extend": ("➕", "the session budget cap is raised"),
}
PRODUCER = {a: v[0] for a, v in FLOW.items()}


def producer_of(rec):
    """Which participant signed a step's message (handles role-dependent steps)."""
    a, o = rec["action"], (rec["object"] or {})
    if a == "dispute_evidence":
        return "Payee" if o.get("role") == "payee" else "Agent"
    if a == "dispute_resolution":
        return "Arbiter" if o.get("resolverRole") == "arbiter" else "Payee"
    return PRODUCER.get(a)


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
    "credentialExpired": "the credential's own validity window has passed",
    "credentialRevoked": "the principal revoked this credential",
    "holderMismatch": "the signer isn't the subject of the credential",
    "budgetExceeded": "this usage would exceed the committed session budget",
    "missingConfirmation": "fresh human approval is required, but none was provided",
    "forgedConfirmation": "the approval wasn't signed by the principal",
    "overRefund": "the refund is larger than the original settlement",
    "noReversalBasis": "there's no upheld resolution to charge back",
    "accountRedirection": "the settlement account isn't bound to the payee's DID (redirection blocked)",
    "settlementNotFinal": "the settlement proof hasn't reached the chain's finality threshold",
    "settlementMismatch": "the settlement proof doesn't match the instructed amount or binding",
}

SCENARIOS = {s["name"]: s for s in sim.load_scenarios()}


def _group_of(name):
    for g, names in GROUPS.items():
        if name in names:
            return g
    return list(GROUPS)[0]


# ---- engine-driven helpers --------------------------------------------------

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


def outcome_of(res):
    """Headline outcome for the banner: kind, colour, emoji, title, sub, machine code."""
    for rec in res["trace"]:
        if rec["outcome"]["outcome"] == "reject":
            code = rec["outcome"]["code"]
            why = WHY.get(code, code)
            return {"color": "#dc2626", "emoji": "⛔", "code": code,
                    "title": "Refused — no money moved",
                    "sub": why[:1].upper() + why[1:] + "."}
    last = None
    for rec in res["trace"]:
        if rec["action"] in ("execute", "close_session", "settle_proof",
                             "escrow_release", "reverse_settle_proof"):
            if rec["outcome"].get("outcome") == "ok" and "status" in rec["outcome"]:
                last = rec["outcome"]
    if last:
        s = last.get("status")
        if s == "completed":
            return {"color": "#059669", "emoji": "✅", "code": None,
                    "title": f"Paid {last.get('settled')}",
                    "sub": "The agent paid the payee on the simulated ledger."}
        if s == "partial":
            return {"color": "#d97706", "emoji": "◑", "code": None,
                    "title": f"Partially settled {last.get('settled')}",
                    "sub": "Only part of the amount could move."}
        if s == "failed":
            return {"color": "#dc2626", "emoji": "⚠️", "code": None,
                    "title": "Settlement failed",
                    "sub": "The simulated ledger had no funds."}
    return {"color": "#059669", "emoji": "✅", "code": None, "title": "Completed", "sub": ""}


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
        a = producer_of(rec) or FLOW[rec["action"]][0]
        b = FLOW[rec["action"]][1]
        used.add(a); used.add(b)
        ok = rec["outcome"]["outcome"] == "ok" and rec["outcome"].get("status") != "failed"
        colour = "#059669" if ok else "#dc2626"
        label = f'{n}. {rec["action"]}'
        amt = rec["params"].get("amount") or rec["params"].get("resolvedAmount")
        if amt:
            label += f'  {amt}'
        dash = "" if ok else ' style=dashed'
        edges.append(f'"{a}" -> "{b}" [label="{label}" color="{colour}" fontcolor="{colour}" penwidth=2{dash}];')
        n += 1
    for role in ["Principal", "Agent", "Payee", "Wallet", "Arbiter", "Ledger"]:
        if role in used:
            colour, icon, _ = ROLE[role]
            lines.append(f'"{role}" [label="{role}" fillcolor="{colour}"];')
    lines += edges
    lines.append('}')
    return "\n".join(lines)


def meter_caption(sess):
    """(progress fraction, caption) for a session step — includes the metered units
    (e.g. tokens) when present."""
    accrued = Decimal(sess.get("accrued") or "0")
    committed = Decimal(sess.get("committed") or "0")
    units = Decimal(sess.get("units") or "0")
    dim = (sess.get("dimension") or "").split(":")[-1] or "units"
    txt = f"{accrued} / {committed} used"
    if units > 0:
        txt = f"{int(units):,} {dim} · " + txt
    frac = float(accrued / committed) if committed > 0 else 0.0
    return min(frac, 1.0), txt


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


# ---- HTML builders ----------------------------------------------------------

def hero_html():
    nodes = []
    for i, (nm, ic, c, verb) in enumerate(MENTAL_MODEL):
        nodes.append(f"<div class='avp-node' style='--c:{c}'><div class='ic'>{ic}</div>"
                     f"<div class='nm'>{nm}</div></div>")
        if i < len(MENTAL_MODEL) - 1:
            nodes.append(f"<div class='avp-arrow'><div class='ln'>&rarr;</div>"
                         f"<div class='vb'>{verb}</div></div>")
    return (
        "<div class='avp-hero'>"
        "<div class='kicker'>AVP-MICRO · AGENT VERIFIABLE MICROPAYMENTS</div>"
        "<h1>Agent payments, <em>simulated</em>.</h1>"
        "<p class='sub'>Walk the trust &amp; authorization protocol end to end — real "
        "<code>ecdsa-jcs-2022</code> signatures, full wallet policy enforcement, settled on a "
        "<b>play-money ledger</b>. No real funds move anywhere.</p>"
        f"<div class='avp-flowmap'>{''.join(nodes)}</div>"
        "</div>"
    )


def cast_html():
    rows = []
    for role, (c, ic, _desc) in ROLE.items():
        rows.append("<div class='avp-cast-row'>"
                    f"<span class='dot' style='background:{c}'></span>"
                    f"<span class='ic'>{ic}</span><b>{role}</b>"
                    f"<span class='ds'>{ROLE_SHORT.get(role, '')}</span></div>")
    return "<div class='avp-cast'>" + "".join(rows) + "</div>"


def scenario_title_html(name, grp):
    return (f"<div style='margin:.1rem 0 .15rem'><span class='avp-pill'>{grp}</span></div>"
            f"<h2 style='margin:.1rem 0 .15rem'>{name.replace('-', ' ')}</h2>")


def outcome_html(o):
    code = f"<div class='mc'>{o['code']}</div>" if o.get("code") else ""
    return (f"<div class='avp-outcome' style='--c:{o['color']}'>"
            f"<div class='em'>{o['emoji']}</div>"
            f"<div><div class='ti'>{o['title']}</div>"
            f"<div class='su'>{o['sub']}</div>{code}</div></div>")


def policy_bullets(p):
    out = []
    if p.get("currency"):
        out.append(f"Currency **{p['currency']}**")
    if p.get("maxPerTransaction"):
        out.append(f"≤ **{p['maxPerTransaction']}** per transaction")
    if p.get("dailyLimit"):
        out.append(f"≤ **{p['dailyLimit']}** per day")
    if p.get("allowedPayees"):
        out.append("payees: " + ", ".join(f"`{x}`" for x in p["allowedPayees"]))
    if p.get("allowedCategories"):
        out.append("categories: " + ", ".join(f"`{x}`" for x in p["allowedCategories"]))
    if p.get("expires"):
        out.append(f"expires **{p['expires']}**")
    return out


# ---- detail renderers -------------------------------------------------------

def render_story(res):
    for rec in res["trace"]:
        action = rec["action"]
        amt = rec["params"].get("amount")
        if action in FLOW:
            _a, b, phrase = FLOW[action]
            a = producer_of(rec) or _a
            ia, ib = ROLE[a][1], ROLE[b][1]
            amt = amt or rec["params"].get("resolvedAmount")
            extra = f" **{amt}**" if amt else ""
            st.markdown(f"**{rec['i'] + 1}.** {ia} **{a}** → {ib} **{b}** — {phrase}{extra}  {chip(rec['outcome'])}")
            if rec["object"]:
                with st.expander("signed message (JSON)"):
                    st.json(rec["object"])
            if action in ("accrue", "close_session"):
                sess = rec.get("session") or {}
                if Decimal(sess.get("committed") or "0") > 0:
                    frac, txt = meter_caption(sess)
                    st.progress(frac, text=f"metered budget: {txt} ({int(frac * 100)}%)")
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
    dids = {"Principal": res["credential"].get("issuer"), "Agent": None,
            "Payee": None, "Wallet": None, "Arbiter": None}
    for rec in res["trace"]:
        o = rec["object"] or {}
        dids["Agent"] = o.get("payer", dids["Agent"])
        dids["Payee"] = o.get("payee", dids["Payee"])
        dids["Wallet"] = o.get("wallet", dids["Wallet"])
        if o.get("confirmedBy"):
            dids["Principal"] = o["confirmedBy"]
        if o.get("arbiter"):
            dids["Arbiter"] = o["arbiter"]
        if o.get("resolverRole") == "arbiter":
            dids["Arbiter"] = o.get("resolvedBy")

    roles = ["Principal", "Agent", "Payee", "Wallet"]
    if any(producer_of(r) == "Arbiter" for r in res["trace"]) or dids["Arbiter"]:
        roles.append("Arbiter")
    cols = st.columns(len(roles))
    for col, role in zip(cols, roles):
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

            mine = [r for r in res["trace"] if producer_of(r) == role]
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


def render_policy(res):
    st.markdown("**What the mandate authorizes**")
    for b in policy_bullets(res["policy"]):
        st.markdown(f"- {b}")
    with st.expander("policy JSON"):
        st.json(res["policy"])
    kind = "AP2 IntentMandate imported via did:web" if res["imported"] else "principal-signed credential"
    st.markdown(f"**Spending Authorization Credential** — _{kind}_")
    if res["imported"]:
        st.caption("verified by the wallet against did:web issuers: " + ", ".join(res["resolver"]))
    with st.expander("credential JSON"):
        st.json(res["credential"])


def render_source(name):
    s = SCENARIOS[name]
    st.caption("Exactly how this use case is declared in `engine/sim-scenarios.json` — "
               "the steps the engine replays. Copy it as a template for your own.")
    st.json({k: s[k] for k in ("name", "description", "policy", "balances", "now", "steps", "finalBalances") if k in s})


def render_walk(name):
    res = sim.run_traced(SCENARIOS[name])
    st.markdown(scenario_title_html(name, _group_of(name)), unsafe_allow_html=True)
    st.markdown(f"<p class='avp-lead'>{res['description']}</p>", unsafe_allow_html=True)
    st.markdown(outcome_html(outcome_of(res)), unsafe_allow_html=True)
    st.write("")

    left, right = st.columns([3, 2], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("**Message flow**")
            st.caption("green = accepted / settled · red dashed = refused · number = step order")
            st.graphviz_chart(flow_dot(res), width="stretch")
    with right:
        with st.container(border=True):
            st.markdown("**Money on the ledger**")
            st.caption("Play money — no real funds move.")
            money_panel(res)
            metered = [r for r in res["trace"] if r["action"] in ("accrue", "close_session")]
            if metered and Decimal((metered[-1].get("session") or {}).get("committed") or "0") > 0:
                frac, txt = meter_caption(metered[-1]["session"])
                st.caption("Session budget — metered total vs committed cap")
                st.progress(frac, text=txt)
    st.write("")

    t1, t2, t3, t4 = st.tabs(["📖 Walkthrough", "👥 By participant", "🔑 Policy & authority", "🧩 Declarative source"])
    with t1:
        render_story(res)
    with t2:
        render_participants(res)
    with t3:
        render_policy(res)
    with t4:
        render_source(name)


# ---- overview & conformance -------------------------------------------------

def goto(name):
    """Callback: jump from the overview straight into walking a scenario."""
    st.session_state.nav_view = "Walk a use case"
    st.session_state.nav_cat = _group_of(name)
    st.session_state.nav_scn = name


def render_overview():
    st.markdown("## All use cases")
    results = {n: sim.run_traced(SCENARIOS[n]) for n in SCENARIOS}
    passing = sum(1 for r in results.values() if r["ok"])
    m1, m2, m3 = st.columns(3)
    m1.metric("Use cases", len(results))
    m2.metric("Behave as declared", f"{passing}/{len(results)}")
    m3.metric("Categories", len(GROUPS))
    st.caption("Each scenario replayed through the engine. ✅ = behaved exactly as its declaration says. "
               "Press **Walk →** to open one.")
    for group, names in GROUPS.items():
        with st.container(border=True):
            st.markdown(f"#### {group}")
            for n in names:
                if n not in results:
                    continue
                r = results[n]
                c0, c1, c2 = st.columns([0.5, 7, 1.3])
                c0.markdown("### ✅" if r["ok"] else "### ❌")
                c1.markdown(f"**{n.replace('-', ' ')}**  \n<span class='avp-muted'>{r['description']}</span>",
                            unsafe_allow_html=True)
                c2.button("Walk →", key=f"go-{n}", on_click=goto, args=(n,), width="stretch")


def _verify_vector(obj):
    """True/False if it carries an ecdsa-jcs-2022 Data Integrity proof; None otherwise
    (an unsigned fixture, a foreign SD-JWT envelope, or a proof-preserving projection
    verified in its own stack)."""
    if isinstance(obj, dict) and isinstance(obj.get("proof"), dict) \
            and obj["proof"].get("cryptosuite") == "ecdsa-jcs-2022":
        try:
            return ac.verify_ecdsa_jcs_2022(obj)
        except Exception:
            return False
    return None


_SKIP = {"keys.json"}  # the resolver fixture (not a conformance object)


def render_conformance():
    st.markdown("## Conformance test vectors")
    if not SPEC_DIR:
        st.warning("Spec repo not found. Set `AVP_SPEC_DIR` to the spec/ directory, or place this "
                   "demo beside the `avp-micro-spec` repo, to list the signed conformance vectors here.")
        return

    bundles, total, verified, fixtures = [], 0, 0, 0
    for title, d in BUNDLES:
        base = SPEC_DIR / d / "test-vectors"
        if not base.exists():
            continue
        files = [f for f in sorted(base.glob("*.json")) if f.name not in _SKIP]
        if not files:
            continue
        items = []
        for f in files:
            total += 1
            try:
                obj = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                items.append((f.name, None, None, f"unreadable ({e})"))
                continue
            t = obj.get("type") if isinstance(obj, dict) else None
            if isinstance(t, list):
                t = next((x for x in t if x != "VerifiableCredential"), t[0])
            v = _verify_vector(obj)
            if v is True:
                verified += 1
            elif v is None:
                fixtures += 1
            items.append((f.name, t, v, obj))
        bundles.append((title, d, items))

    m1, m2, m3 = st.columns(3)
    m1.metric("Signed vectors", total)
    m2.metric("Proofs verify", verified)
    m3.metric("Fixtures / foreign", fixtures)
    st.caption(f"Read live from `{SPEC_DIR}`. ✅ = its `ecdsa-jcs-2022` proof verifies here; native AVP objects "
               "are signed, while foreign SD-JWT envelopes and proof-preserving projections are verified in "
               "their own stack.")

    for title, d, items in bundles:
        with st.container(border=True):
            st.markdown(f"#### {title}  ·  `{d}/`")
            for name, t, v, obj in items:
                if obj is None or not isinstance(obj, (dict, list)):
                    st.markdown(f"- ⚠️ `{name}` — {t if t else obj}")
                    continue
                if v is True:
                    badge = ":green[✅ proof verifies]"
                elif v is False:
                    badge = ":red[⛔ proof FAILS]"
                else:
                    badge = ":gray[— fixture / verified in its own stack]"
                with st.expander(f"`{name}` — {t or 'fixture'}  ·  {badge}"):
                    st.json(obj)


# ---- layout -----------------------------------------------------------------

st.markdown(CSS, unsafe_allow_html=True)
st.markdown(hero_html(), unsafe_allow_html=True)

st.session_state.setdefault("nav_view", "Walk a use case")
st.session_state.setdefault("nav_cat", list(GROUPS)[0])
st.session_state.setdefault("nav_scn", GROUPS[list(GROUPS)[0]][0])

with st.sidebar:
    st.markdown("### Explore")
    view = st.radio(
        "View",
        ["Walk a use case", "All use cases", "Conformance vectors"],
        key="nav_view",
        captions=["one scenario, end to end", "every scenario at a glance", "signed spec test vectors"],
    )
    if view == "Walk a use case":
        grp = st.selectbox("Category", list(GROUPS), key="nav_cat")
        if st.session_state.get("nav_scn") not in GROUPS[grp]:
            st.session_state.nav_scn = GROUPS[grp][0]
        st.radio("Use case", GROUPS[grp], key="nav_scn", format_func=lambda s: s.replace("-", " "))

    st.divider()
    st.markdown("**Cast**")
    st.markdown(cast_html(), unsafe_allow_html=True)
    st.divider()
    st.caption(f"{len(SCENARIOS)} use cases · engine vendored from avp-micro-spec · play money only")

st.divider()
if view == "Walk a use case":
    render_walk(st.session_state.nav_scn)
elif view == "All use cases":
    render_overview()
else:
    render_conformance()
