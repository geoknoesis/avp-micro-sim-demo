"""Plain-language explainers for each simulator use case.

A teaching/UI layer over `engine/sim-scenarios.json`: each scenario name maps to a
three-part explainer rendered in the "Walk a use case" view —

    what  : what happens, in plain language (the flow)
    why   : why it matters (the security or economic property demonstrated)
    watch : what to watch for (the outcome / refusal to look for on screen)

Kept out of the canonical scenario data on purpose — these are presentation, not
protocol. Markdown is allowed (e.g. `code` spans). Keyed by scenario `name`.
"""

EXPLAINERS = {

    # ⓪ Delegate authority (issuance)
    "issue-delegate-authority": {
        "what": "The principal (a person or organization) issues a `SpendingAuthorizationCredential` to the agent's DID — caps, allowed payees, currency, validity — signs it, and the agent then makes a payment that stays within those bounds.",
        "why": "Delegation done right: authority is a signed, bounded credential the agent *holds*, not a shared password or an unlimited card. Anyone can later verify who granted what.",
        "watch": "The payment settles (✅), and the **Policy & authority** tab shows the exact terms the principal signed.",
    },
    "issue-wrong-subject": {
        "what": "The credential is issued to a key the agent does **not** control. When the agent tries to authorize a payment, the wallet checks that the authorization is signed by the credential's subject key — and it isn't.",
        "why": "A credential only grants authority to the holder of its subject key. Binding it to a DID the agent controls stops a stolen or mis-addressed credential from being used by the wrong party.",
        "watch": "Refused with a holder mismatch (⛔) — verification fails before any policy or money check.",
    },
    "issue-expired-credential": {
        "what": "The principal issues a credential whose validity window has already ended, then the agent tries to spend under it.",
        "why": "Authority is time-bounded. The wallet checks `validFrom`/`validUntil`, so expired delegations can't be revived.",
        "watch": "Refused (⛔) — the credential is outside its validity window.",
    },
    "issue-then-revoked": {
        "what": "The agent spends once under a fresh credential. The principal then revokes it (via the status list), and the agent's next charge is checked against status and refused.",
        "why": "Delegation must be retractable. Revocation is an operational, tested step — the principal can cut the agent off at any time, and verifiers honor it.",
        "watch": "The first charge settles (✅); after revocation the second is refused (⛔).",
    },
    "issue-ap2-intent": {
        "what": "Instead of a native credential, the user issues a Google **AP2** `IntentMandate` (an SD-JWT-VC signed under `did:web`). The agent imports it across the bridge and spends; the wallet verifies the embedded foreign signature.",
        "why": "Authority can originate in another ecosystem and still be honored here — and it roots in the *user's* DID, not the bridge. One agent's mandate works across stacks without re-issuance.",
        "watch": "Settles (✅); the **Policy & authority** tab shows the imported AP2 mandate projected into the native view.",
    },

    # ① One-off payments
    "one-off-happy-path": {
        "what": "The agent requests a price (quote), signs an authorization committing to that exact quote and request, and the wallet — after checking the amount is within the credential's caps and the payee is allowed — settles 1.00 and receives a signed receipt.",
        "why": "The baseline forward flow. Every object is independently signed and the wallet enforces policy *before* any money moves, so authority is proven, not assumed.",
        "watch": "Outcome ✅ settled 1.00; four signed objects (quote → authorize → execute → receipt) in the message flow.",
    },
    "over-per-transaction-cap": {
        "what": "The payee quotes more than the credential's per-transaction cap. The wallet compares the quote to the mandate, sees it exceeds `maxPerTransaction`, and refuses.",
        "why": "Caps are enforced by the verifier at spend time, not merely declared. A compromised or over-eager agent can't exceed the limit its principal set, even holding a valid credential.",
        "watch": "Refused (⛔ over per-transaction cap) — no authorization is consumed and no funds move.",
    },
    "payee-not-allowed": {
        "what": "The quote comes from a payee that isn't in the credential's `allowedPayees` list. The wallet checks the payee DID against the allowlist and refuses.",
        "why": "Principals can confine an agent to specific counterparties, so a confused or hijacked agent can't pay an attacker.",
        "watch": "Refused (⛔ payee not allowed).",
    },
    "category-not-allowed": {
        "what": "The authorization is for a service category outside the credential's `allowedCategories`. The wallet refuses on category scope.",
        "why": "Authority can be scoped by *domain of service*, not just amount — finer-grained control over what the agent may buy.",
        "watch": "Refused (⛔ category not allowed).",
    },
    "daily-limit-exceeded": {
        "what": "Two payments on the same day; the second pushes the running total past `dailyLimit`. The wallet tracks cumulative same-day spend and refuses the second.",
        "why": "Rolling limits constrain *aggregate* spend, not just single transactions — protection against many small drains.",
        "watch": "The first settles (✅); the second is refused (⛔ daily limit).",
    },
    "daily-limit-resets-next-day": {
        "what": "The same spend that would breach the daily limit succeeds once the clock advances a day and the window resets.",
        "why": "Limits are windowed, not permanent — normal recurring activity resumes automatically the next day.",
        "watch": "After the clock advances, the charge settles (✅).",
    },
    "authorization-expired": {
        "what": "An authorization is presented after its short expiry window has passed. The wallet checks the `expires` timestamp and refuses.",
        "why": "Authorizations are short-lived so a captured one can't be used later. Freshness is enforced.",
        "watch": "Refused (⛔ expired).",
    },
    "replayed-authorization": {
        "what": "A previously consumed authorization (same `nonce`) is presented again. The wallet remembers consumed nonces and refuses the replay.",
        "why": "Each authorization is single-use; replay protection stops an old approval from being charged twice.",
        "watch": "Refused (⛔ replay / nonce reuse).",
    },

    # ② Binding & integrity
    "tampered-quote": {
        "what": "After the agent signs an authorization committing to the quote's digest, the quote is mutated. The wallet recomputes the digest and detects the mismatch.",
        "why": "The authorization is cryptographically bound to the *exact* quote; you can't swap in different terms after approval.",
        "watch": "Refused (⛔ quote tampered / digest mismatch).",
    },
    "amount-mismatch": {
        "what": "The authorization cites a quote but states a different amount than the quote does. The wallet cross-checks and refuses.",
        "why": "Amount is bound between quote and authorization, so the charge can't drift from what was agreed.",
        "watch": "Refused (⛔ amount mismatch).",
    },
    "currency-mismatch": {
        "what": "The quote is in a currency the credential doesn't authorize. The wallet checks currency against the mandate and refuses.",
        "why": "Spending authority is currency-scoped; an agent authorized for USD can't be charged in another currency.",
        "watch": "Refused (⛔ currency mismatch).",
    },
    "corrupted-signature": {
        "what": "The authorization's proof is corrupted. Signature verification fails immediately — before any policy evaluation.",
        "why": "Cryptographic verification is the first gate; malformed or forged proofs never reach business logic.",
        "watch": "Refused (⛔ signature verification failed).",
    },

    # ③ Settlement outcomes
    "insufficient-funds": {
        "what": "Policy passes, but the simulated rail can't settle (the agent lacks funds). The wallet records a *failed* execution rather than a receipt.",
        "why": "Authorization and settlement are distinct; a valid authorization doesn't guarantee value moved — the outcome is reported honestly.",
        "watch": "Execution status **failed**; no receipt, no money moved.",
    },
    "partial-settlement": {
        "what": "The rail settles less than the authorized amount. The wallet records the execution as *partial* with the actual settled value.",
        "why": "Real rails sometimes move only part of the amount; the protocol captures partial outcomes so reconciliation stays accurate.",
        "watch": "Outcome ◑ partially settled, with the smaller amount on the ledger.",
    },

    # ④ Human-present approval
    "human-present-confirmed": {
        "what": "A flow that requires fresh human approval includes a valid `PurchaseConfirmation` signed by the principal; the wallet accepts it and settles.",
        "why": "Some spends should need a human in the loop; the confirmation is a signed, verifiable artifact, not a checkbox.",
        "watch": "Settles (✅) with the confirmation present.",
    },
    "human-present-missing": {
        "what": "Fresh human approval is required, but no `PurchaseConfirmation` is supplied. The wallet refuses.",
        "why": "The human-approval requirement is enforced — absence blocks the spend.",
        "watch": "Refused (⛔ confirmation missing).",
    },
    "human-present-forged": {
        "what": "A confirmation is present but signed by the agent itself, not the principal named as `confirmedBy`. The wallet checks the signer and rejects it.",
        "why": "Self-approval is not approval; the confirmation must come from the designated human/principal key.",
        "watch": "Refused (⛔ forged confirmation / signer mismatch).",
    },

    # ⑤ Streaming / metered
    "streaming-happy": {
        "what": "A metered session: open the session, authorize a budget, accrue usage in signed increments within the cap, then close and settle the total.",
        "why": "For usage-billed services, trust is established once per session and each increment is signed — efficient and auditable, not a fresh authorization per call.",
        "watch": "Settles the accrued total (✅); the **session-budget gauge** stays under the cap.",
    },
    "streaming-budget-exceeded": {
        "what": "Accruals climb until the next increment would exceed the committed session budget; metering halts at the cap.",
        "why": "Session budgets bound *total* metered spend, so a runaway meter can't overrun what was authorized.",
        "watch": "Metering stops (⛔ budget exceeded) at the cap.",
    },
    "streaming-extend-budget": {
        "what": "Mid-session, the cap is raised via an extension plus a fresh budget authorization, which admits further accrual.",
        "why": "Budgets can be lifted deliberately and verifiably mid-flight, without tearing down the session.",
        "watch": "After the extension, more usage accrues and settles (✅).",
    },
    "streaming-token-usage": {
        "what": "An agent streams from an LLM and pays per output token: usage accrues as token batches over time, the running cost climbs toward the budget, and the wallet settles the metered total at close.",
        "why": "True pay-per-token micro-billing — exactly the high-frequency, tiny-amount pattern cards can't serve — with each batch attributable.",
        "watch": "The budget gauge climbs with token count; settles the metered total (✅).",
    },
    "streaming-metered-session": {
        "what": "A live metered session with per-unit pricing: usage accrues over time, the running total climbs toward the budget cap, and the wallet settles the total at close.",
        "why": "General metered consumption (minutes, rows, calls) billed continuously under one signed budget.",
        "watch": "The gauge approaches the cap; settles the total (✅).",
    },

    # ⑥ AP2 bridge (imported authority)
    "bridge-imported-mandate-happy": {
        "what": "The agent's authority is an AP2 `IntentMandate` imported across the bridge; a one-off payment runs under it, and the wallet verifies the embedded foreign signature via `did:web`.",
        "why": "Imported cross-ecosystem authority behaves like native authority for ordinary payments — interop without re-issuance.",
        "watch": "Settles (✅); authority verified via the foreign `did:web` signature.",
    },
    "bridge-imported-over-cap": {
        "what": "A quote above the imported AP2 mandate's cap is refused — the policy carried inside the foreign mandate is enforced just like a native one.",
        "why": "Bridging preserves the mandate's limits; importing doesn't loosen policy.",
        "watch": "Refused (⛔ over cap) under the imported mandate.",
    },
    "bridge-human-present-imported": {
        "what": "An AP2 human-present cart approval is imported as a `PurchaseConfirmation` projection and satisfies the fresh-approval requirement.",
        "why": "A human approval made in the AP2 world is honored here — the human-in-the-loop property crosses the bridge.",
        "watch": "Settles (✅) with the imported confirmation.",
    },
    "bridge-human-present-imported-missing": {
        "what": "The imported mandate requires fresh human approval, but none is present; the payment is refused.",
        "why": "Imported flows keep their approval requirements; the bridge doesn't waive them.",
        "watch": "Refused (⛔ confirmation missing).",
    },

    # ⑦ Refunds, reversals & disputes
    "refund-full": {
        "what": "After a settled payment the payee refunds the full amount; a wallet-signed reversal records the money moving back and the payer acknowledges it.",
        "why": "The reverse value-flow is first-class and signed — refunds are auditable, not out-of-band.",
        "watch": "The full amount returns to the agent (✅ reversal + acknowledgement).",
    },
    "refund-partial": {
        "what": "The payee issues a partial goodwill refund; only part of the original payment moves back.",
        "why": "Partial returns are supported and bound to the original receipt.",
        "watch": "Part of the amount returns; the ledger reflects the partial reversal.",
    },
    "over-refund-rejected": {
        "what": "A refund larger than the original settlement is attempted and refused.",
        "why": "You can't return more than was paid; the reverse flow is bounded by the original.",
        "watch": "Refused (⛔ over-refund).",
    },
    "dispute-upheld-chargeback": {
        "what": "The payer disputes the charge; both sides exchange evidence; the payee offers partial; an arbiter upholds 0.75, and the wallet reverses exactly that amount.",
        "why": "The full adversarial lifecycle — dispute, evidence, resolution, arbiter — converges on a signed reversal of the decided amount.",
        "watch": "0.75 reverses to the agent after the arbiter's upheld resolution; an ⚖️ Arbiter joins the flow.",
    },
    "dispute-rejected": {
        "what": "The payee rejects the dispute; with no upheld resolution, a chargeback is refused and no money moves back.",
        "why": "Disputes don't automatically reverse funds — an upheld resolution is required, protecting payees from unilateral clawbacks.",
        "watch": "No reversal (⛔ chargeback refused); balances unchanged.",
    },
    "dispute-withdrawn": {
        "what": "The payer withdraws the dispute; nothing is reversed.",
        "why": "A withdrawn dispute closes cleanly with no value movement, leaving an auditable trail.",
        "watch": "No money moves; the dispute closes as withdrawn.",
    },

    # ⑧ On-chain settlement binding
    "settle-evm-direct": {
        "what": "The authorization is bound to an EVM stablecoin (USDC) rail with a `did:pkh` payee; the wallet verifies a final `SettlementProof` and the money moves on-chain.",
        "why": "The authorization layer binds to a real public rail — the proof of on-chain finality is itself a signed object.",
        "watch": "Settles (✅) once the `SettlementProof` is final.",
    },
    "settle-x402-account-binding": {
        "what": "On the x402 rail, the payee signs a `PayeeAccountBinding` proving it controls the destination account; the instruction references it and the wallet settles only to the bound account.",
        "why": "Binds a DID to an on-chain account so funds can only go to an account the payee provably controls.",
        "watch": "Settles (✅) to the bound account.",
    },
    "settle-account-redirection": {
        "what": "The settlement instruction names an account that is *not* bound to the payee's DID. The wallet detects the unbound account and refuses to settle.",
        "why": "Anti-redirection — an attacker can't substitute their own account for the payee's, even with an otherwise valid instruction.",
        "watch": "Refused (⛔ account not bound / redirection blocked).",
    },
    "settle-not-final": {
        "what": "The `SettlementProof` hasn't reached the required confirmation threshold; the wallet treats it as not final and withholds value.",
        "why": "Finality is checked explicitly — value isn't released on an unconfirmed transaction.",
        "watch": "Value not released (⛔ not final / pending confirmations).",
    },
    "settle-amount-mismatch": {
        "what": "The `SettlementProof` reports a settled amount below what was instructed; the wallet rejects the binding.",
        "why": "The on-chain amount must match the instruction — underpayment doesn't satisfy the obligation.",
        "watch": "Refused (⛔ amount mismatch).",
    },
    "settle-lightning-escrow": {
        "what": "The payment is bound to a Lightning hold-invoice in escrow mode: funds are locked, and only when the payee reveals the preimage does the `SettlementProof` become final and release to the payee.",
        "why": "Conditional, atomic settlement on a non-EVM rail — value is held until delivery is proven, then released, all bound to the same authorization.",
        "watch": "Lock → preimage reveal → release (✅); the payee is paid only on reveal.",
    },
    "settle-evm-escrow-timeout": {
        "what": "An EVM escrow times out before the payee delivers; the locked funds are refunded to the payer and the payee is never paid.",
        "why": "Escrow protects the payer — non-delivery within the window returns the money automatically.",
        "watch": "Funds refunded to the agent (✅ refund); the payee gets nothing.",
    },
    "settle-reverse": {
        "what": "After a settled EVM payment, a compensating transfer with payer and payee swapped moves the value back to the agent — the settlement-layer image of a dispute reversal.",
        "why": "Shows how an authorization-layer reversal (refund/chargeback) is realized on-chain as a compensating transaction.",
        "watch": "Value returns to the agent via the reverse transfer (✅).",
    },
    "settle-card-stripe": {
        "what": "The authorization is settled over a **card rail** through a processor (Stripe). The wallet binds it to a payee-signed `ProcessorAccountBinding`, instructs an authorize-then-capture, and the payee returns a **payee-attested** `AttestedSettlementProof` that the card was captured — then the money moves.",
        "why": "Card settlement happens inside a closed processor, so finality isn't publicly verifiable: the proof embeds the processor's result and roots trust in the payee (or the named `did:web` processor). Authorize/capture maps cleanly onto the escrow lifecycle.",
        "watch": "Settles (✅); the instruction is `mode: escrow` / `captureMode: auth-capture` and the attestation `status` is `captured`.",
    },
    "settle-rtp-push": {
        "what": "The authorization is settled over an **instant bank rail** (FedNow / RTP) as a direct push. The payee returns a payee-attested `AttestedSettlementProof` that the transfer settled, and the money moves.",
        "why": "RTP is push and **irrevocable**, so there is no escrow — the proof attests settlement after the fact. Same attested-finality model as card, a different scheme.",
        "watch": "Settles (✅); the instruction is `mode: direct` with `scheme: fednow` (no escrow), attestation `status` `settled`.",
    },
    "settle-card-redirection": {
        "what": "The card instruction names a processor account whose `ProcessorAccountBinding` is controlled by an **attacker**, not the authorized payee. The wallet checks the binding and refuses to settle.",
        "why": "Anti-redirection holds on closed-processor rails just as on-chain: funds may only go to an account the *authorized payee* signed for, even with an otherwise valid authorization.",
        "watch": "Refused (⛔ account redirection); no money moves.",
    },
}
