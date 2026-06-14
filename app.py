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
    ("On-chain settlement binding", "settlement"), ("Transport (HTTP 402)", "transport"),
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

/* transport: HTTP-on-the-wire conversation */
.wire-req, .wire-res{ font-family:'IBM Plex Mono',monospace; font-size:.82rem;
  border:1px solid var(--line); border-radius:11px; background:var(--panel); padding:.55rem .8rem; }
.wire-req{ border-left:4px solid #2563eb; }
.wire-res{ border-left:4px solid var(--accent); margin:.45rem 0 .15rem 1.6rem; }
.wire-line{ font-weight:600; color:var(--ink); display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; }
.wire-line .pa{ word-break:break-all; }
.wire-hdr{ color:var(--muted); font-size:.75rem; margin-top:.34rem; line-height:1.55; }
.wire-hdr b{ color:var(--ink); font-weight:600; }
.m-badge, .s-badge{ font-weight:700; border-radius:6px; padding:.05rem .45rem; font-size:.72rem; color:#fff; }
.wire-dir{ color:var(--muted); font-size:.72rem; margin:.5rem 0 .1rem 1.6rem; }
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


# ---- transport (HTTP 402 wire binding) --------------------------------------

# the wire layer's mental model: discovery, then the 402 challenge dance
TXP_FLOW = [
    ("Discover", "🛰️", "#6d28d9", "GET /.well-known"),
    ("402 Challenge", "🚧", "#d97706", "quote + nonce"),
    ("Authorize", "🤖", "#2563eb", "echo the nonce"),
    ("200 + Receipt", "🧾", "#059669", ""),
]
TXP_NS = "https://w3id.org/avp-micro/transport/v1#"
TXP_WHY = {  # transport error-code (local name) -> plain explanation
    "over-cap": "the amount is above the agent's per-transaction limit",
    "currency-mismatch": "the currency isn't the one the mandate authorizes",
    "amount-mismatch": "the authorization's amount doesn't match the quote",
    "daily-limit-exceeded": "this would exceed the agent's daily spending limit",
    "budget-exceeded": "this would exceed the committed session budget",
    "payee-not-allowed": "this payee isn't on the agent's allow-list",
    "category-not-allowed": "this category isn't permitted by the mandate",
    "expired": "the quote or authorization has expired",
    "challenge-expired": "the 402 challenge expired — fetch a fresh one",
    "idempotency-conflict": "the Idempotency-Key was reused with a different body",
    "double-spend": "this authorization was already settled once",
    "nonce-reuse": "this challenge nonce was already used (replay blocked)",
    "credential-revoked": "the principal revoked the credential",
    "unauthorized": "the submission signature or credential chain failed",
    "malformed-request": "the request body was malformed",
}
_METHOD_C = {"GET": "#2563eb", "POST": "#7c3aed", "PUT": "#d97706", "DELETE": "#dc2626"}
_REASON = {200: "OK", 201: "Created", 400: "Bad Request", 401: "Unauthorized",
           402: "Payment Required", 403: "Forbidden", 409: "Conflict",
           422: "Unprocessable Content", 502: "Bad Gateway", 503: "Service Unavailable"}


def _status_color(s):
    if 200 <= s < 300:
        return "#059669"
    if s == 402:
        return "#d97706"
    return "#dc2626"


def _txp(name):
    return json.loads((SPEC_DIR / "transport" / "test-vectors" / name).read_text(encoding="utf-8"))


def _body_type(body):
    if not isinstance(body, dict):
        return "JSON"
    t = body.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "VerifiableCredential"), t[0])
    if isinstance(t, str) and t.startswith(TXP_NS):
        return "ProblemDetails"
    if t:
        return t
    if "challenge" in body and "quote" in body:
        return "402 body { challenge, quote }"
    return "JSON"


def _headers_html(h):
    if not h:
        return ""
    return "<div class='wire-hdr'>" + "<br>".join(
        f"<b>{k}:</b> {v}" for k, v in h.items()) + "</div>"


def _wire_card(kind, top_html, headers):
    st.markdown(f"<div class='wire-{kind}'><div class='wire-line'>{top_html}</div>"
                f"{_headers_html(headers)}</div>", unsafe_allow_html=True)


def _body_expander(label, body):
    if isinstance(body, (dict, list)):
        t = _body_type(body)
        v = _verify_vector(body) if isinstance(body, dict) else None
        if isinstance(body, dict) and "challenge" in body and isinstance(body.get("challenge"), dict):
            v = _verify_vector(body["challenge"])  # the embedded signed challenge
        sig = "  ·  :green[✅ signed proof verifies]" if v is True else (
            "  ·  :red[⛔ proof FAILS]" if v is False else "")
        with st.expander(f"{label} — {t}{sig}"):
            st.json(body)


def _render_exchange(log):
    st.caption(log.get("description", ""))
    # the challenge nonce the server issued in this exchange (for the echo check)
    nonce = None
    for stp in log["steps"]:
        rb = stp["response"].get("body")
        if isinstance(rb, dict) and isinstance(rb.get("challenge"), dict):
            nonce = rb["challenge"].get("challenge")
    # the canonical payments objects the transport objects wrap (for digest checks)
    try:
        authz_c = json.loads((SPEC_DIR / "payments" / "test-vectors"
                              / "02-payment-authorization.json").read_text(encoding="utf-8"))
    except Exception:
        authz_c = None

    for i, stp in enumerate(log["steps"], 1):
        req, res = stp["request"], stp["response"]
        with st.container(border=True):
            st.markdown(f"**Step {i}**")
            # --- request ---
            mc = _METHOD_C.get(req["method"], "#6b7280")
            _wire_card("req",
                       f"<span class='m-badge' style='background:{mc}'>{req['method']}</span>"
                       f"<span class='pa'>{req['path']}</span>", req.get("headers", {}))
            rb = req.get("body")
            if _body_type(rb) == "SessionBudgetAuthorization":
                st.caption("commits the session budget cap the payee meters against.")
            if _body_type(rb) == "AuthorizationSubmission":
                echo = rb.get("challenge") == nonce
                st.markdown(":green[✓ echoes the server challenge nonce — binds this submission "
                            "to *this* 402 (anti-replay)]" if echo
                            else ":red[✗ challenge nonce does not match]")
                if authz_c is not None:
                    bound = rb.get("authorizationDigest") == ac.jcs_digest(authz_c)
                    st.markdown(f":green[✓ authorizationDigest binds `{short(rb.get('authorization'))}`]"
                                if bound else ":red[✗ authorizationDigest mismatch]")
                if req.get("headers", {}).get("Idempotency-Key"):
                    st.caption("Idempotency-Key makes the retry safe — a repeat returns the same "
                               "receipt; a different body → 409 idempotency-conflict.")
            _body_expander("request body", rb)

            st.markdown("<div class='wire-dir'>↓ response</div>", unsafe_allow_html=True)
            # --- response ---
            sc = _status_color(res["status"])
            _wire_card("res",
                       f"<span class='s-badge' style='background:{sc}'>{res['status']}</span>"
                       f"<span>{_REASON.get(res['status'], '')}</span>", res.get("headers", {}))
            sb = res.get("body")
            bt = _body_type(sb)
            if bt == "402 body { challenge, quote }":
                ch, q = sb["challenge"], sb["quote"]
                bound = ch.get("quoteDigest") == ac.jcs_digest(q)
                st.markdown(f":green[✓ quoteDigest binds the offered quote `{short(q.get('id'))}`]"
                            if bound else ":red[✗ quoteDigest does not match the quote]")
                st.caption(f"server challenge nonce `{ch.get('challenge')}` · expires {ch.get('expires')} "
                           "— the client must echo the nonce on its retry.")
            elif bt == "ProblemDetails":
                code = (sb.get("type") or "").rsplit("#", 1)[-1]
                why = TXP_WHY.get(code, code)
                st.markdown(f":red[**⛔ {code}** — {why}.]")
                if sb.get("field"):
                    st.caption(f"offending field: `{sb['field']}`")
            elif bt == "PaymentReceipt":
                st.markdown(":green[✓ delivered — payee-signed PaymentReceipt]")
            elif bt == "PaymentExecution":
                st.markdown(":green[✓ wallet-signed PaymentExecution]")
            elif bt == "UsageSession":
                st.markdown(":green[✓ metered session — UsageSession]")
            elif bt == "UsageAccrual":
                st.markdown(":green[✓ incremental metered usage — UsageAccrual]")
            elif bt == "SettlementProof":
                fin = sb.get("finality")
                tone = "green" if fin == "final" else "orange"
                st.markdown(f":{tone}[✓ SettlementProof — finality **{fin}**]")
            if res.get("headers", {}).get("Location"):
                st.caption("↪ Location — the client polls this URL until the SettlementProof is final.")
            _body_expander("response body", sb)


def _render_discovery(sd):
    st.caption("`GET /.well-known/avp-micro` → a payee-signed **ServiceDescription**: the agent "
               "learns endpoints, accepted issuers, and settlement rails before transacting.")
    v = _verify_vector(sd)
    badge = ":green[✅ proof verifies]" if v is True else (
        ":red[⛔ proof FAILS]" if v is False else ":gray[—]")
    st.markdown(f"**Payee** `{short(sd.get('payee'))}`  ·  {badge}")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Accepted settlement rails**")
        for r in sd.get("acceptedSettlementRails", []):
            st.markdown(f"- `{r.rsplit('#', 1)[-1]}`")
        st.markdown("**Accepted credential issuers**")
        for iss in sd.get("acceptedCredentialIssuers", []):
            st.markdown(f"- `{short(iss)}`")
    with c2:
        st.markdown("**Supported bundles**")
        for ns, ver in (sd.get("supportedBundles") or {}).items():
            st.markdown(f"- `{ns.rsplit('/', 2)[-2] if ns.endswith('v1') else ns}` → {ver}")

    st.markdown("**Endpoints advertised**")
    eps = sd.get("endpoints") or {}
    st.table([{"operation": k, "URL template": v} for k, v in eps.items()])
    with st.expander("ServiceDescription JSON"):
        st.json(sd)


def render_transport():
    st.markdown("## Transport — the HTTP 402 challenge")
    if not SPEC_DIR or not (SPEC_DIR / "transport" / "test-vectors").exists():
        st.warning("Transport bundle not found. Set `AVP_SPEC_DIR` to the spec/ directory (and ensure "
                   "the transport bundle is present) to illustrate the wire protocol here.")
        return
    st.markdown(
        "<p class='avp-lead'>The other bundles define <em>messages</em>; this one defines the "
        "<em>wire</em>. An agent and a payee run the whole flow over HTTP using a "
        "<b>402 Payment Required</b> challenge. Below are the spec's own signed example exchanges — "
        "the same bytes the conformance vectors carry — rendered as the HTTP conversation.</p>",
        unsafe_allow_html=True)

    nodes = []
    for i, (nm, ic, c, verb) in enumerate(TXP_FLOW):
        nodes.append(f"<div class='avp-node' style='--c:{c}'><div class='ic'>{ic}</div>"
                     f"<div class='nm'>{nm}</div></div>")
        if i < len(TXP_FLOW) - 1:
            nodes.append(f"<div class='avp-arrow'><div class='ln'>&rarr;</div>"
                         f"<div class='vb'>{verb}</div></div>")
    st.markdown(f"<div class='avp-flowmap'>{''.join(nodes)}</div>", unsafe_allow_html=True)
    st.write("")

    tabs = st.tabs(["💳 402 happy path", "🧾 explicit quote", "📡 streaming",
                    "⏳ async settle", "🔁 idempotency", "🚫 replay", "⛔ over-cap",
                    "🛰️ discovery"])
    with tabs[0]:
        _render_exchange(_txp("40-exchange-402-flow.json"))
    with tabs[1]:
        _render_exchange(_txp("42-exchange-quote-flow.json"))
    with tabs[2]:
        _render_exchange(_txp("43-exchange-streaming.json"))
    with tabs[3]:
        _render_exchange(_txp("44-exchange-async-settlement.json"))
    with tabs[4]:
        _render_exchange(_txp("45-exchange-idempotency.json"))
    with tabs[5]:
        _render_exchange(_txp("46-exchange-replay.json"))
    with tabs[6]:
        _render_exchange(_txp("41-exchange-over-cap.json"))
    with tabs[7]:
        _render_discovery(_txp("00-service-description.json"))


def render_live():
    st.markdown("## Live — run a real 402 exchange")
    st.markdown("<p class='avp-lead'>Set the mandate policy and the request, then run the exchange "
                "for real: the quote, the 402 challenge, the authorization, and the wallet's verdict are "
                "produced live with real <code>ecdsa-jcs-2022</code> signatures and the reference wallet's "
                "actual policy enforcement — nothing is mocked.</p>", unsafe_allow_html=True)
    import live  # noqa: E402  (shares the engine + server.py)

    c1, c2, c3 = st.columns(3)
    amount = c1.text_input("Amount", "1.00")
    cap = c2.text_input("Cap (maxPerTransaction)", "5.00")
    currency = c3.selectbox("Currency", ["USD", "EUR"], index=0)
    c4, c5, c6 = st.columns(3)
    payee_allowed = c4.toggle("Payee on allow-list", value=True)
    require_conf = c5.toggle("Require human approval", value=False)
    provide_conf = c6.toggle("…and provide it", value=False, disabled=not require_conf)

    params = {"amount": amount, "maxPerTransaction": cap, "currency": currency,
              "payeeAllowed": payee_allowed, "requireConfirmation": require_conf,
              "provideConfirmation": provide_conf}
    try:
        result = live.build_exchange(params)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not run the exchange: {e}")
        return

    v = result["verdict"]
    if v.get("outcome") == "reject":
        st.markdown(outcome_html({
            "color": "#dc2626", "emoji": "⛔", "code": v.get("code"),
            "title": "Refused — no money moved",
            "sub": (WHY.get(v.get("code"), v.get("code")) or "").capitalize() + "."}),
            unsafe_allow_html=True)
    else:
        s = v.get("status", "completed")
        title = f"Accepted — {s}" + (f" {v.get('settled')}" if v.get("settled") else "")
        st.markdown(outcome_html({
            "color": "#059669", "emoji": "✅", "code": None, "title": title,
            "sub": "The wallet verified the chain, enforced policy, and settled on the play ledger."}),
            unsafe_allow_html=True)
    st.write("")
    _render_exchange(result["exchange"])

    with st.expander("Run it as a real local HTTP server (`server.py`)"):
        pa = "allowed" if payee_allowed else "blocked"
        st.caption("Same logic, served over real HTTP on localhost:8402 — a repeated authorized call "
                   "returns 409 nonce-reuse (single-use challenge).")
        st.code(
            "python server.py\n"
            f'curl -i "http://localhost:8402/resource/premium?amount={amount}&cap={cap}&payee={pa}"\n'
            f'curl -i "http://localhost:8402/resource/premium?amount={amount}&cap={cap}&payee={pa}" '
            '-H "Authorization: AVP-Micro retry"',
            language="bash")


def render_conformance_profile():
    st.markdown("## Wallet conformance")
    prof = (SPEC_DIR / "conformance" / "profile.json") if SPEC_DIR else None
    if not prof or not prof.exists():
        st.warning("Wallet Conformance Profile not found in the spec checkout. Set `AVP_SPEC_DIR` "
                   "to the spec/ directory to certify the reference engine here.")
        return
    import conformance as conf  # vendored engine
    report = conf.evaluate(profile_path=prof)
    rows = report["rows"]
    cats = []
    for r in rows:
        if r["category"] not in cats:
            cats.append(r["category"])
    m1, m2, m3 = st.columns(3)
    m1.metric("Requirements", report["total"])
    m2.metric("Satisfied", f"{report['satisfied']}/{report['total']}")
    m3.metric("Categories", len(cats))
    st.caption("The bundled **reference engine** certified against the normative "
               "**Wallet Conformance Profile** (`conformance/profile.json`), read live from the "
               "spec. ✅ = the engine behaved exactly as the requirement declares. To certify your "
               "own wallet, implement a `WalletAdapter` (see the profile README).")
    for cat in cats:
        crows = [r for r in rows if r["category"] == cat]
        npass = sum(1 for r in crows if r["passed"])
        with st.container(border=True):
            st.markdown(f"#### {cat} — {npass}/{len(crows)}")
            for r in crows:
                badge = ":green[✅]" if r["passed"] else ":red[⛔]"
                detail = (f"scenario `{r['scenario']}` → expect `{r['expected']}`"
                          + ("" if r["passed"] else f" · observed `{r['observed']}`"))
                st.markdown(f"{badge} **{r['id']}** <span class='avp-muted'>({r['level']})</span> "
                            f"{r['statement']}  \n<span class='avp-muted'>{detail}</span>",
                            unsafe_allow_html=True)


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
        ["Walk a use case", "All use cases", "Transport (HTTP 402)", "Live (try it)",
         "Wallet conformance", "Conformance vectors"],
        key="nav_view",
        captions=["one scenario, end to end", "every scenario at a glance",
                  "the HTTP wire protocol", "run a real 402 exchange",
                  "the normative WCP profile", "signed spec test vectors"],
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
elif view == "Transport (HTTP 402)":
    render_transport()
elif view == "Live (try it)":
    render_live()
elif view == "Wallet conformance":
    render_conformance_profile()
else:
    render_conformance()
