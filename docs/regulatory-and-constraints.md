# Regulatory, Contractual and Operational Constraints

Status: draft v0.1, 2026-10-16. Companion to `design.md` section 2 (constraints
register) and section 11 (OTC), `risk-manager.md`, `execution.md`,
`journal-and-reporting.md`, `operations.md`, `agent-operating-model.md`.

This document is the synthesis of three research reports in `research/`
(R1 legal status and manipulation, R2 broker and market data terms, R3 tax,
records and OTC). Those reports carry the detail and every source URL; this
document carries the conclusions, the design consequences, and the list of
things a professional must confirm. Nothing here is legal or tax advice.

**How to read the ratings.** Each finding is marked with the research
confidence (high, medium, low) and whether a professional should confirm it
before the system depends on it. Research was done from search excerpts of
primary sources because vendor and regulator sites were unreachable from the
research environment; items marked unconfirmed are listed in section 13.

---

## 1. The one-paragraph answer

An individual trading only their own money, in an account in their own name,
with software they wrote, needs no license, registration or regulatory filing
of any kind, and no rule from 2024 to 2026 about AI or automation changes
that. Three things would change it instantly: handling anyone else's money,
publishing or selling signals, or pooling money. The rules that do bind this
system are the ones that bind every trader: anti-manipulation law, the
broker's customer agreement, the market data subscriber agreement, and the
tax code. Each of them turns into concrete design rules below, and most of
those rules are cheap. The expensive one is tax: the wash-sale rule will
touch nearly every losing re-entry, and the mark-to-market election that
removes it cannot take effect before tax year 2027.

---

## 2. Legal status and the three doors (R1 section 1)

**Finding.** Own-account trading falls under the Exchange Act trader
exclusion from "dealer" (the 2024 rule that would have widened "dealer" was
vacated in November 2024 and the appeal dropped). The Advisers Act needs
compensation, being in the business, and advising others; none is present.
The Market Access Rule's pre-trade controls sit on Alpaca, not on us.
Confidence high. No professional needed for the current scope.

**The three doors**, each of which requires counsel before opening:

| Door | What triggers it | What follows |
|---|---|---|
| Other people's money | Any compensated management or advice for anyone, including friends and extended family. "Compensation" is read very broadly. | State adviser registration, often from the first client in your home state; the family office exclusion covers family only and requires a company structure |
| Selling or publishing signals | A paid or public feed of actionable calls, especially while holding the position | Adviser registration; the publisher exclusion covers only impersonal, disinterested, regularly scheduled publications. Scalping liability under Rule 10b-5 regardless |
| Pooling money | Any vehicle that takes outside capital | Reg D offering, Investment Company Act exclusions, adviser status for the manager |

**Design consequences.** No multi-account abstraction in the code. No public
dashboard, bot or feed of signals. The README and this document state the
single-user scope so a future feature does not cross a door by accident.

---

## 3. Market conduct: manipulation law and what the 2025 to 2026 cases teach (R1 section 2)

**Finding.** Spoofing and layering in equities are charged under Exchange Act
sections 9(a)(2) and 10(b) and Rule 10b-5, which bind any person. Four SEC
actions against individuals in 2025 and 2026 (Cole, Khachatryan, Wang with a
parallel criminal plea, Cerisano) share one fact pattern: orders placed on the
side opposite the trader's real intent, placed to be cancelled, in thin books,
mostly outside regular hours. Three of the four involved a broker warning,
account closure, and then opening accounts elsewhere or in others' names.
Penalties ran from roughly $350,000 to $1.5 million plus five-year trading
bans. Intent is inferred statistically: Coscia's order-to-trade ratio was 16
to 1 against peers at 1 to 2.6 to 1. Confidence high.

**What is structurally safe.** A long-only system that only places orders it
wants filled, at or inside the spread, one working order per side per symbol,
never holding a buy and a sell open in the same name except a protective exit
on a filled position, is outside the charged conduct by construction.
Entering at the ask and chasing is a good-faith attempt to trade. The exit
ladder that reprices one tick toward the bid every 20 seconds is the mirror
image of layering: it moves toward the market, its size equals the real
position, and 20 seconds is slow by any surveillance standard.

**Conduct invariants** (adopt as risk manager and execution rules):

1. One working order per side per symbol. Never an open buy while a sell is
   open in the same symbol unless the sell is a protective exit on a filled
   position.
2. Every order is placed at or inside the spread. No resting orders at
   multiple price levels away from the touch.
3. Cancel-replace, never cancel-then-new, for repricing. Each replacement
   moves toward the market.
4. Regular hours only, 09:30 to 16:00 ET. All four cases exploited extended
   hours.
5. No entries after 15:30 and no working sells after 15:45, so nothing is
   active in the closing minutes. This also keeps clear of marking-the-close.
6. Log orders, cancels, replaces and fills per symbol per day. Alert when
   cancels plus replaces per fill exceed 10 to 1 on any day; investigate above
   20 to 1.
7. Sanity-reject any limit more than 5 percent from the last trade.
8. A per-minute order submission cap and automatic shutdown on repeated
   rejections, borrowed from FINRA Regulatory Notice 15-09.
9. Never split activity across brokers or use accounts in others' names.
10. If a broker ever sends a trading-pattern inquiry, answer truthfully from
    the journal and consult counsel first.

---

## 4. Account, margin and broker terms (R2 sections 1 and 4)

**Findings.**

- All Alpaca accounts are margin accounts; there is no cash account product.
  Leverage is capped by the account `multiplier` (1, 2 or 4). Under $2,000
  equity the account is "limited margin" at 1x and can still reuse unsettled
  proceeds because Alpaca covers the settlement float. Confidence medium-high.
- The Pattern Day Trader rule is gone (FINRA Regulatory Notice 26-10,
  effective June 4, 2026; interpretive follow-up Notice 26-11 on May 19, 2026).
  Alpaca switched on day one. An intraday margin deficit triggers a call that
  Alpaca says must be met within two business days; unmet at the close of the
  fifth business day means a 90-day restriction; there is a de minimis of
  $1,000 or 5 percent of equity. Alpaca's pre-trade checks reject orders that
  would create a deficit. The old day-trade API fields were removed July 6,
  2026. Confidence high.
- A long-only account whose gross exposure never exceeds its cash cannot
  produce a negative intraday margin level, so a margin call can only arise
  through edge cases: end-of-day regulatory fee debits against zero cash,
  over-fills or duplicate orders, or a house requirement change. Confidence
  medium-high; it follows from the definitions but Alpaca may add house rules.
- Low-priced stocks: securities under $3 are not marginable and have no
  collateral value; Alpaca's house maintenance is 100 percent for longs under
  $2.50 and 50 percent from $2.50 to $6. The per-symbol truth is the assets
  endpoint (`tradable`, `marginable`, `maintenance_margin_requirement`),
  which can change without notice. Confidence medium-high.
- Customer agreement: the customer owns every order that reasonably appears
  authentic, including those placed by their own software; Alpaca disclaims
  trading losses and may restrict or close an account without notice. There
  is no separate algorithmic trading agreement, only an automated-systems
  risk acknowledgment. Trading API limit is about 200 requests per minute
  per account, returning 429 on excess with no evidence of punitive action.
  Prices need at most two decimals at or above $1 and four below. Regulatory
  fees are accrued intraday and debited as one end-of-day total.
- Reg T free-riding and good-faith violations are cash-account rules and do
  not apply to this setup. The margin-account Reg T payment period is
  settlement plus two business days.

**Design consequences.**

- The leverage gate stays ours, not the broker's: cap open notional at cash
  minus a fee buffer, computed from our own marks, and never size from the
  broker's buying power.
- Treat any intraday margin call notice or negative cash as a halt condition
  with automatic flattening and a LOCKED session until explained.
- Read the assets endpoint daily before PREFLIGHT; refuse anything not
  tradable; record the maintenance requirement per symbol in the journal.
- Token-bucket the trading API at about 3 requests per second with 429
  backoff that tolerates missing rate-limit headers.
- Expect rejections rather than calls as the first symptom of any margin
  problem, and handle the rejection codes.
- Keep equity above $2,000 so Alpaca does not downgrade the account.

**Ask Alpaca in writing** (operations task, before phase 2 ends): whether a
multiplier-1 account can ever receive an intraday margin call; the current
maintenance tiers for $1 to $5 stocks; how working orders and cancel
requests are handled during regulatory halts on seasoned stocks; the
customer agreement's erroneous-trade clause for equities.

---

## 5. Market data licensing (R2 sections 2 and 3)

**Finding.** The non-professional subscriber status that makes SIP data cost
about $1 per month instead of tens of dollars per feed plus non-display fees
in the thousands depends on three things: a natural person, personal
non-business use, an account in the person's own name, and no registration
with any securities regulator or exchange and not acting as an adviser. An
LLC, trust or any entity account is professional automatically. Running your
own algorithm on the data is "non-display use" in concept, but the CTA fee
schedule exempts non-professionals from non-display, access and device fees,
so no extra license is needed while the status is honest. Misclassification
is a contractual exposure to back-billing at professional rates plus audit
costs. Both Alpaca Algo Trader Plus and Massive license individual plans for
personal use only: no redistribution, no derived products reaching third
parties. Massive's Market Data Terms contain display-only and
delete-on-termination clauses that conflict with its own FAQ. Confidence high
on definitions, medium on fee amounts, low on the LLM-specific treatment.

**The LLM question.** Nasdaq's 2025 Data AI Policy treats distribution of its
data through LLMs or RAG, and model training on it, as license-governed and
potentially fee-liable for licensees. It is written for vendors and firms,
but the operative constraint for us is the vendor's no-third-party clause:
sending raw real-time quotes to an external model API arguably furnishes data
to a third party. Derived artifacts (signals, decisions, P&L, summaries) do
not recreate the feed and fit the derived-data definition.

**Design consequences.**

- Brokerage and data accounts stay in the individual's name. Forming an LLC
  for the trading activity means professional data rates and re-papering;
  that is a CPA plus budget decision, not a default.
- The agent and any runtime LLM see derived artifacts only: journal rows,
  metrics, candidate summaries. Never raw quotes, trades or bars from a live
  SIP feed. This is already the agent operating model's design; this is the
  contractual reason for it.
- No public dashboards, shared scanners, or posted tick data.
- Prefer Alpaca-sourced history for long-term archives. If Massive is used
  for survivorship-free history, get its written confirmation on storage and
  non-display use first, and keep a documented deletion policy.
- Re-answer the non-professional questionnaire honestly if anything changes.

---

## 6. Market structure risks (R1 sections 3, 4 and 6; R3 section 6)

**Clearly erroneous executions.** During regular hours a fill in a stock
covered by Limit Up Limit Down is not reviewable as clearly erroneous when
bands were in effect, so regular-hours fills in our universe are effectively
final. Outside regular hours a sub-$25 stock's fill can be broken at more
than 20 percent from the reference price within a 30-minute review window.
Confidence high. Consequence: regular hours only, and still reconcile against
broker activity at close and next morning rather than trusting the local fill
log, with an explicit "fill reversed" event path.

**Halts and suspensions.** LULD pauses are 5 minutes, extendable. News
pending halts typically run 30 to 60 minutes or longer; "additional
information requested" halts can run days. SEC trading suspensions are
unannounced, take effect at 09:30, run 10 business days, and after one a
delisted name may never regain a quote. Alpaca holds open orders pending
through a halt and accepts new orders for halted names, confirmed only from
an IPO FAQ. Confidence high on mechanics, medium-low on Alpaca handling.
Consequence: on any halt, cancel working orders in the symbol so nothing
fills blindly on the reopening auction, flag the position frozen, and gate
re-entry after resumption. The session controller already does this; the
pending-orders behavior is why cancellation must be explicit.

**Beneficial ownership.** Schedule 13D or 13G filing starts at 5 percent of
shares outstanding, with deadlines in business days. Above 10 percent, every
same-day round trip is a strict-liability matched transaction under Section
16(b), with a plaintiffs' bar watching filings. Post-reverse-split listed
stocks exist with under one million shares outstanding, so 5 percent can be a
$100,000 to $300,000 position. Confidence high on thresholds, medium on
prevalence. Consequence: an unconditional cap of 1 percent of shares
outstanding per symbol, rejection when the share count is missing,
invalidation of cached counts on any split, and a journaled maximum intraday
ownership percentage per symbol.

**Tick sizes.** The Reg NMS amendments introduced half-penny quoting for
tick-constrained stocks with a November 2025 compliance date (implementation
timing unconfirmed). Many $1 to $5 names are tick-constrained. Consequence:
the execution adapter supports $0.005 increments where the exchange list says
so, and round lots stay 100 shares across this universe.

---

## 7. Broker protections and outages (R2 section 5)

Alpaca Securities is self-clearing and a Nasdaq member since October 2025.
SIPC covers $500,000 per customer including $250,000 cash on a net-equity
basis; bank sweep balances sit outside SIPC. Alpaca carries excess SIPC via
Lloyd's. The 2025 to 2026 status record shows recurring short degradations,
two multi-hour Trading API incidents in August 2026 including incorrect
position updates after sells, and a two-week paper-trading failure in
November 2025 that never appeared on the status page. Confidence high on
protections, medium on outage history.

**Design consequences.** Assume the API can go dark mid-session: stop
placing orders, attempt cancel-all, alert with the status page link, and do
not assume cancels succeeded until confirmed. After any incident, rebuild
positions from account activities, not from the positions endpoint. Treat
paper trading as a weaker reliability signal than live. The operations
playbooks for API down and reconciliation mismatch cover this.

---

## 8. Taxes and records (R3 sections 1 to 4)

**Treatment.** Every intraday trade is a short-term gain or loss at ordinary
rates (10 to 37 percent for 2026, made permanent in 2025). Net investment
income tax of 3.8 percent applies above $200,000 single or $250,000 joint,
even with trader tax status. Trading income has no withholding, so quarterly
estimated payments are needed; the prior-year safe harbor (100 percent of
last year's tax, 110 percent above $150,000) is the simplest rule for a
system whose P&L is unknown in advance. Confidence high.

**The wash-sale rule is the central tax constraint.** A loss on a sale is
disallowed if the same stock is bought within 30 days before or after, and
the disallowed loss rolls into the basis of the replacement lot. For a system
re-entering the same names, nearly every losing trade will be a wash sale.
Within a year the chain nets out once the name is left alone for 31 days.
The damage is at year end: a December loss washed by a January re-entry
defers the loss into the next tax year and inflates this year's taxable
income. The broker's 1099-B applies the rule only within one account and one
CUSIP, and lot matching can differ from an independent computation, so the
taxpayer owns the full calculation. Thousands of trades go on Form 8949 by an
attached statement under Exception 2. Confidence high.

**Trader tax status and the mark-to-market election.** Trader tax status is
a facts-and-circumstances position: substantial, continuous, regular activity
aimed at short-term swings. Practitioner benchmarks are roughly 500 to 1,000
or more trades a year, trading on about 75 percent of market days, average
holding well under 31 days, several hours a day. Days traded matter more than
trade count; part-time status is the main weakness, though a trader who
worked only the last hour of the day has won. The Section 475(f)
mark-to-market election makes gains and losses ordinary, removes the
wash-sale rule and the $3,000 capital loss cap, and marks open positions at
year end. An existing individual must elect by the unextended due date of the
prior year's return, so **the earliest effective year is now 2027, with the
statement due April 15, 2027**. The IRS consistently denies late-election
relief. A new entity can elect within two months and fifteen days of
formation. The election is sticky for at least a year. Confidence high on
mechanics, low-medium on whether this system qualifies.

**Records.** The IRS wants basis and trade records for at least three years
after filing, six for large understatements, seven for worthless securities.
An append-only journal plus broker statements and 1099-Bs exceeds this. An
individual has no FINRA or SEC recordkeeping duty; those rules bind
broker-dealers. Confidence high.

**Entities.** An S corporation is the only route to health insurance and
retirement plan deductions because trading gains are not earned income. Costs
are payroll, franchise taxes, separate returns, and professional market data
classification. Practitioners say it pays only with consistent six-figure
profits. Entirely a CPA question.

**Design consequences.**

- A tax lot engine that computes FIFO lots and wash-sale adjustments
  independently, reconciled against the 1099-B each January. The journal
  design's 8949-style export becomes a full engine, not a flag.
- A configurable **year-end blackout**: flat in every name with an open wash
  chain by a date in mid-December, no re-entry in those names for 31 days.
  Unless and until 475(f) is elected, this is the single most important tax
  control in the system.
- A **trader-status evidence export** from the journal: trades per month,
  trading days as a percent of market days, holding period distribution,
  hours of activity, dollar volume, and a continuity chart. This is what the
  Tax Court looks at.
- A quarterly estimated-tax reminder with year-to-date realized P&L and both
  safe-harbor targets.
- Configuration items for state of residence (some states allow no capital
  loss carryforward) and tax mode (capital versus 475 ordinary), so reports
  can switch between Schedule D and Form 4797 presentation.
- Retain journal exports, statements and returns indefinitely in a durable
  format outside the live database.
- Never hold investment positions in the trading account.

**Consult a CPA** who specializes in trader taxation before the first full
tax year, specifically on: the year-end wash-sale strategy for 2026, whether
the live pattern supports trader tax status, and whether to make the 475(f)
election for 2027 by April 15, 2027.

---

## 9. The OTC extension (R3 section 5; design.md section 11)

Exchange-listed stocks under $5 are not "penny stocks" under Rule 3a51-1, so
the penny stock disclosure and suitability rules do not touch the v1
universe. They would apply to the OTC extension, as broker-side duties: a
signed risk disclosure before the first trade, suitability paperwork only for
solicited trades. Since the 2021 amendments to Rule 15c2-11, names without
current public information fall to the Expert Market or Grey Market, where
retail accounts are mostly sell-only and a position can lose all liquidity.
OTC Markets' tiers are now OTCQX, OTCQB, OTCID (July 2025), Pink Limited and
Expert Market, plus the Caveat Emptor flag that most brokers treat as
liquidate-only. An SEC suspension breaks quoting eligibility so quotes rarely
resume. Brokers with APIs that allow OTC: Interactive Brokers ($0.005 per
share fixed, $1 minimum, 1 percent maximum), TradeStation ($0.005 per share,
$1 minimum, $50 maximum, 5 percent of notional cap). Tradier does not.
Schwab's API support is unconfirmed. Confidence high on rules, medium on
broker schedules.

Design consequences are in `design.md` section 11 and stand: OTC is a
separate venue class with a tier gate (OTCQX, OTCQB, OTCID only), a
liquidate-or-block rule on downgrade or flag, a per-share commission model,
and an explicit model of total liquidity loss. Listed names in v1 are still
exposed to delisting into OTC; monitor compliance notices for held names.

---

## 10. Watch list of pending changes (R3 section 6; R1 section 5)

| Item | Status | Relevance |
|---|---|---|
| Intraday margin phase-in | Brokers may run legacy PDT logic until October 20, 2027 | Keep a feature flag; never hardcode PDT |
| Reg NMS half-penny ticks, odd-lot data | Compliance dates November 2025 and May 2026; implementation timing unconfirmed | Execution tick logic |
| Wall Street Tax Act (S. 2127) financial transaction tax | Referred to committee, no movement | 0.2 percent round trip would be material; keep a cost-model parameter |
| Digital asset wash-sale bills | Active in 2026 | Stocks already covered; no effect |
| SEC 15c2-11 equity-only proposal (March 2026) | Proposed | OTC extension only |
| SEC or FINRA AI rules for individuals | None exist; the 2023 predictive analytics proposal was withdrawn June 2025 | No obligation; adopt FINRA 15-09 controls voluntarily |

Re-check each January: tax brackets, Form 8949 instructions, FINRA and SEC
fee rates, and any Section 1091 amendment.

---

## 11. Design changes required by this review

These are the deltas against the component documents. Each will be carried
into its target document in its own change.

| Change | Target document | Source section |
|---|---|---|
| Ownership cap: max shares per symbol 1 percent of shares outstanding; reject when count missing; invalidate on split | `risk-manager.md` rule chain; `data-layer.md` symbol_attributes | 6 |
| One working order per side per symbol; no open buy while a sell is open except a protective exit | `risk-manager.md` invariants; `execution.md` | 3 |
| Cash cap with fee buffer, computed from own marks, never from buying power | `risk-manager.md` leverage gate wording | 4 |
| Cancel-plus-replace per fill ratio logged per symbol per day; alert at 10 to 1 | `journal-and-reporting.md` metrics; `operations.md` monitoring | 3 |
| Limit price sanity gate: reject more than 5 percent from last trade | `risk-manager.md` | 3, 6 |
| Order submission rate cap per minute; shutdown on repeated rejects | `execution.md`; `session-controller.md` | 3, 4 |
| Cancel working orders on any halt in the symbol, explicitly, because Alpaca holds them pending | `session-controller.md` HALTED_EXPOSURE; `execution.md` | 6 |
| Half-penny tick support where the exchange list applies | `execution.md` pricing | 6 |
| Intraday margin call notice or negative cash is a halt condition into LOCKED | `session-controller.md`; `operations.md` playbook 8 | 4 |
| Daily assets-endpoint read before PREFLIGHT; maintenance requirement journaled | `session-controller.md` PREFLIGHT; `data-layer.md` | 4 |
| Year-end wash-sale blackout, configurable dates, off when tax mode is 475 | `risk-manager.md` time gates; `screener.md` exclusion list; `operations.md` annual routine | 8 |
| Tax lot engine with wash-sale adjustments; 1099-B reconciliation each January | `journal-and-reporting.md` | 8 |
| Trader-status evidence export | `journal-and-reporting.md` reports | 8 |
| Quarterly estimated-tax reminder | `operations.md` routines | 8 |
| Config: state of residence, tax mode | `operations.md` config files | 8 |
| LLM and agent see derived artifacts only, never raw SIP data | `agent-operating-model.md` access matrix (already true; add the contractual reason) | 5 |
| Written questions to Alpaca and Massive before phase 2 exit | `operations.md` phase gates | 4, 5 |
| Rebuild positions from account activities after incidents, not the positions endpoint | `execution.md` reconciliation; `operations.md` playbooks | 7 |
| Single-user, own-account scope stated in README | `README.md` | 2 |

---

## 12. Professional consultations

| Who | When | What to bring |
|---|---|---|
| CPA specializing in trader taxation | Before the end of 2026 | The journal's trader-status evidence export, the year-end wash chain report, the 475(f) decision for 2027, state of residence, and the entity question |
| Securities attorney | Only if a door in section 2 opens, if short selling or two-sided logic is ever added, or immediately if a broker sends a trading-pattern inquiry | The journal and this document |
| Alpaca support, in writing | Before the phase 2 exit gate | The four questions in section 4 |
| Massive, in writing | Before relying on a Massive archive | Storage, non-display and deletion terms for individual plans |

---

## 13. Unconfirmed items

Consolidated from the three reports. None blocks phase 1; all should be
closed before phase 3.

- Whether Alpaca `max_margin_multiplier` 1 disables all credit and whether
  such an account can receive an intraday margin call.
- Exact semantics of Alpaca's per-asset margin requirement fields.
- Alpaca's customer agreement wording on erroneous trades for equities, and
  its handling of cancels during regulatory halts on seasoned stocks.
- Algo Trader Plus concurrent WebSocket connection cap.
- Current 2026 professional SIP display and non-display fee amounts.
- Massive's 2025 Market Data Terms as applied to individual plans.
- Exact interpretive text of FINRA Regulatory Notice 26-11.
- Whether Schedule 13G passive amendments above 10 percent are due in 2 or
  5 business days.
- Whether Nasdaq's excessive order fee ratio is still 100 to 1.
- Whether the Reg NMS tick and round-lot amendments took effect on schedule.
- Exact 2026 tax bracket cutoffs (trade press differs by about $25), and
  Pennsylvania and Washington state treatment of short-term gains and losses.
- Schwab Trader API support for OTC symbols; IBKR OTC-specific exceptions.
- Alpaca's official 2025 incident history and open-order handling during
  API outages.

## 14. Changelog

- v0.1: initial synthesis of research reports R1, R2 and R3.
