# R2 — Broker and market-data contractual constraints

Research date: 2026-10-16. Method: web search only (WebFetch/curl blocked), so every finding
below rests on search excerpts of primary documents rather than full-text reads. Items marked
**UNCONFIRMED** could not be verified from an excerpt and must be checked against the live
document before the system relies on them. Scope: one individual, own money, Alpaca margin
account with leverage disabled by configuration, long-only, exchange-listed US stocks $1–$5,
intraday only; data from Alpaca Algo Trader Plus (SIP) with Massive (formerly Polygon.io) as
fallback; an AI coding agent that holds no broker credentials.

---

## 1. Alpaca customer agreement, API terms, rate limits, margin and low-priced stocks

### Short answer
Alpaca has no separate "algorithmic trading agreement". Automated trading is covered by the
Customer Agreement's automated-systems risk acknowledgment, the Terms and Conditions (which
define the API as part of "the Service"), and a "Risks of Automated Trading" disclosure. The
customer is responsible for every order that reasonably appears authentic, Alpaca disclaims
trading losses and consequential damages, and Alpaca may restrict, prohibit or terminate at
its discretion without prior notice. Trading API rate limit is ~200 requests/min per account
(429 on excess; no evidence of account penalties). **All Alpaca accounts are margin accounts**
(no cash accounts), and the account's `multiplier` / `max_margin_multiplier` config ("1", "2",
"4") is how leverage is capped. Alpaca implemented FINRA's intraday-margin framework on
2026-06-04: an intraday margin deficit (IMD) triggers a call that Alpaca says must be met
within two business days, an unmet deficit at close of the fifth business day triggers the
90-day restriction, and there is a de minimis threshold ($1,000 or 5% of equity, whichever is
lower). Low-priced stocks: sub-$3 securities are not marginable and carry no collateral value;
longs under $2.50 carry 100% maintenance, $2.50–$6 carry 50% (older docs said 30%). No public
"restricted symbol list" was found; the `/v2/assets` fields (`tradable`, `marginable`,
`maintenance_margin_requirement`, `margin_requirement_long`) are the per-symbol source of truth.

### Detail

**Agreements that govern automated/API trading**
- The Customer Agreement (library file `AcctAppMarginAndCustAgmt.pdf`; versions seen from
  2020 through V23.2025.05) has the customer acknowledge that use of "Automated Systems"
  entails risks (interruption, delays, errors in information, design/functioning defects) that
  can cause substantial harm, that use of the API and services is at the customer's own risk,
  and that Alpaca is not liable for consequential damages including trading losses or for
  inaccurate/delayed data. Orders received electronically are accepted and processed as long
  as they reasonably appear authentic; the customer bears responsibility for orders placed
  through the account (including by an "authorized delegate").
- Alpaca Terms and Conditions (`TermsAndConditions.pdf`) define the website, API and mobile
  app collectively as "the Service" and are supplemental to the customer agreements.
- The Disclosures library lists an "Alpaca Risks of Automated Trading" document and a
  companion Learn article: set up continuous monitoring/alerting for connectivity loss, power
  failure or crash; watch for anomalies that produce errant, missing or duplicated orders;
  monitor conditional orders for reasonability. Alpaca does not document a customer-facing
  "kill switch" (UNCONFIRMED whether one exists beyond cancel-all-orders / close-all-positions
  endpoints).
- Third-party access to an account is at the user's own risk; Alpaca does not warrant against
  resulting losses. Relevant because the AI coding agent must not hold live keys.
- Erroneous trades: the Options Agreement explicitly lets Alpaca cancel an executed trade it
  judges to contain a data, clerical or similar processing error, even one caused by a third
  party. The equities agreement excerpt did not surface an identical clause (UNCONFIRMED), but
  exchange clearly-erroneous rules apply regardless. There is no clause shifting liability for
  a customer's own software errors to Alpaca; the customer owns them.
- Prohibited activity/closure: Alpaca may "prohibit or restrict the trading of securities, or
  the substitution of securities" in any account at its discretion; may limit platform access
  and terminate an account without prior notice; closing does not affect prior obligations.
  Where Alpaca and third-party documents conflict, "the most restrictive terms shall prevail".
  Specific restriction triggers found: repeated fractional orders with notional under $0.01;
  stale tax forms. No text found that bans trading bots or algorithms (Alpaca markets itself
  for them); no explicit market-manipulation clause surfaced in excerpts (UNCONFIRMED; assume
  general securities law applies).

**Rate limits and what happens on excess**
- Trading API: ~200 requests/min per account (paper and live counted separately), per Alpaca
  staff on the forum; not raised by a paid data plan. Elite (≥$30k net deposits) can be raised
  to 1,000/min, but one support page says the account is then designated "non-retail" and
  routed via institutional smart routers rather than wholesalers — check before accepting.
- Market Data REST: 200/min on Basic, 10,000/min on Algo Trader Plus.
- Excess returns HTTP 429 with `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
  `X-RateLimit-Reset` headers (a 2026 forum thread reports the headers sometimes missing on
  429s). Alpaca's guidance: exponential back-off, do not retry before the reset time. No source
  describes account suspension for rate-limit abuse.
- Streaming: exceeding the plan's concurrent-connection allowance returns an in-band error
  code 406. Basic allows one stock stream connection; ATP's cap is UNCONFIRMED.
- Order precision: limit/stop prices ≥ $1.00 max 2 decimals, < $1.00 max 4 decimals; excess
  precision is rejected with code 42210000 ("sub-penny increment does not fulfill minimum
  pricing criteria").

**Margin agreement, account type and leverage configuration**
- Alpaca support: "we do not offer cash accounts. All accounts are set up as margin
  accounts." Accounts under $2,000 equity are "limited margin" (multiplier 1) and can still
  reuse unsettled proceeds because Alpaca "covers the float" at no cost.
- Account `multiplier` field: 1 = limited margin, 2 = Reg T margin, 4 = intraday (formerly
  PDT) margin. Default is 1 under $2,000 equity and 2 above. `max_margin_multiplier` in
  account configurations accepts "1", "2", "4" (type changed to string 2026-07-07 changelog).
  Whether "1" fully disables all credit extension or only caps buying power at 1x is
  UNCONFIRMED from docs; the float-coverage statement implies some settlement-period credit
  always exists.
- Margin Disclosure Statement: Alpaca can raise house maintenance at any time without
  advance notice; can require more collateral on low-priced, thinly traded or volatile
  securities; customer cannot choose which security is liquidated and is not entitled to an
  extension; Alpaca may liquidate to cover a shortfall.

**Post-June-2026 intraday margin at Alpaca**
- Effective 2026-06-04 (Alpaca blog, docs, X post). Trading API accounts receive "intraday
  margin calls" replacing day-trade margin calls.
- Docs page "The Intraday Margin Rule": if an IMD occurs a margin call is issued and "must be
  satisfied within two business days" (house standard — FINRA only says "as promptly as
  possible"); an IMD unmet at close of the fifth business day → 90-day restriction on new debit
  balances / short positions; de minimis: a call is generally not triggered if the unmet
  deficit is < $1,000 or 5% of equity, whichever is lower. Satisfy via net deposits or
  IML-increasing actions (e.g., liquidating positions).
- Alpaca blog: real-time pre-trade checks reject orders that would create or increase an IMD.
- Customer Agreement (2025+): "if My margin account incurs an intraday margin deficit, Alpaca
  will require Me to satisfy such deficit as promptly as possible"; Alpaca may phase in the
  standards under RN 26-10.
- There is a dedicated docs page "Intraday Margin Rule for Non-Leverage Margin Accounts"
  (states the $25k minimum no longer applies and firms may keep house requirements). Its
  precise treatment of multiplier-1 accounts could not be read (UNCONFIRMED) — ask Alpaca
  support whether a multiplier-1 account can ever receive an intraday margin call.
- API changes: `daytrade_count`, `daytrading_buying_power`, `pattern_day_trader`,
  `dtbp_check` and PDT endpoints deprecated 2026-06-03 and removed 2026-07-06; use
  `buying_power`. Alpaca commented on SR-FINRA-2025-017 (comment letter on sec.gov).

**Low-priced / volatile stocks**
- Margin Disclosure: equities under $3/share may not be purchased on margin or deposited as
  collateral; if a held stock falls below $3 it has no collateral value.
- Margin docs (current): long share price < $2.50 → 100% of EOD market value maintenance;
  $2.50–$6.00 → 50%. Older v1.1 docs: ≥ $2.50 → 30%. Treat the current (stricter) tiers as
  live and read the per-asset fields.
- `/v2/assets` fields: `tradable`, `marginable`, `shortable`, `easy_to_borrow`,
  `fractionable`, `maintenance_margin_requirement`, `margin_requirement_long`,
  `margin_requirement_short`. Non-marginable symbols show 100%. Official field semantics
  (percent vs ratio) UNCONFIRMED from excerpts — verify in the API reference.
- No public list of restricted symbols found. OTC is not supported except a small set of ADRs;
  Alpaca "only provides data for exchange listed stocks"; a stock delisted to OTC becomes
  sell-only or untradable.
- Regulatory fees (SEC Section 31, FINRA TAF, CAT) are accrued intraday and charged as a
  cumulative EOD total rounded up to the cent; they come out of sale proceeds / buying power.

### Design implications
- Treat `GET /v2/assets` (`tradable`, `marginable`, `maintenance_margin_requirement`) as a
  daily pre-market gate; refuse symbols that are not tradable or whose price is < $1 or that
  the system cannot price-format correctly (4 decimals below $1, 2 at/above).
- Enforce "leverage disabled" in the system itself, not just via `max_margin_multiplier=1`:
  cap total open notional at `cash` (not `buying_power`), keep a cash buffer for EOD
  regulatory-fee debits, and never rely on `buying_power` for sizing.
- Build a Trading API token bucket at ≤ ~3 req/s with 429 back-off that honors
  `X-RateLimit-Reset` and tolerates missing headers; separate budget for market-data REST.
- Implement the monitoring Alpaca's disclosure asks for: heartbeat, duplicate-order guard
  (client order IDs), order reconciliation against `/v2/orders` and `/v2/positions`, and a
  flatten-and-halt routine on connectivity loss.
- Expect Alpaca to change house margin requirements without notice; re-read asset fields
  daily rather than caching them.
- API keys stay out of the coding agent's reach (paper keys for development only; live keys
  in a secrets manager on the runtime host).
- Watch the account for any `intraday margin call` notice and halt new entries until cleared.

**Confidence:** medium-high on agreement structure, rate limits, margin tiers and the
June-2026 implementation; medium on the exact current wording (several agreement versions
circulate); low on multiplier-1 treatment under the intraday rule.
**Consult a professional?** Not required for an individual trading own funds, but ask Alpaca
support in writing about (a) multiplier-1 accounts and intraday margin calls, (b) the
current maintenance tiers for $1–$5 stocks.

### Sources
- Customer Agreement (library): https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf
- Customer Agreement V23.2025.05 (copy): https://musaffa.com/assets/08_Alpaca-Customer-Agreement.pdf
- Terms and Conditions: https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf
- Disclosures library: https://alpaca.markets/disclosures
- Risks of automated trading systems: https://alpaca.markets/learn/risks-automated-trading-systems
- Margin Disclosure Statement: https://files.alpaca.markets/disclosures/library/MarginDiscStmt.pdf
- Margin and Short Selling (docs): https://docs.alpaca.markets/us/docs/margin-and-short-selling
- The Intraday Margin Rule (docs): https://docs.alpaca.markets/us/docs/the-intraday-margin-rule
- Understanding FINRA's New Intraday Margin Rule (docs): https://docs.alpaca.markets/us/docs/understanding-finras-new-intraday-margin-rule-and-the-end-of-pdt
- Intraday Margin Rule for Non-Leverage Margin Accounts: https://docs.alpaca.markets/us/docs/intraday-margin-rule-for-non-leverage-margin-accounts
- Alpaca blog on new framework: https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/
- PDT fields deprecation changelog: https://docs.alpaca.markets/us/changelog/2026-06-03-pdt-651df23
- Account configurations changelog 2026-07-07: https://docs.alpaca.markets/us/changelog/2026-07-07-admin-configurations-ad3805b
- Trading Account docs: https://docs.alpaca.markets/us/docs/account-plans
- Cash accounts support page: https://alpaca.markets/support/alpaca-cash-accounts
- Unsettled funds: https://alpaca.markets/learn/understanding-unsettled-funds
- Rate limit forum (staff): https://forum.alpaca.markets/t/is-there-a-way-to-increase-the-200-min-api-call-limit-for-the-trading-endpoint/18110
- Increase API rate limit support page: https://alpaca.markets/support/increase-api-rate-limit
- X-RateLimit headers missing thread: https://forum.alpaca.markets/t/x-ratelimit-headers-missing-on-429-responses/19404
- Placing Orders (precision): https://docs.alpaca.markets/docs/orders-at-alpaca
- Regulatory fees: https://docs.alpaca.markets/us/docs/regulatory-fees
- OTC support thread: https://forum.alpaca.markets/t/over-the-counter-otc-market-support/729
- Alpaca Elite: https://alpaca.markets/elite
- Alpaca comment letter on SR-FINRA-2025-017: https://www.sec.gov/comments/sr-finra-2025-017/srfinra2025017-700567-2197875.pdf

---

## 2. Market-data subscriber status, non-display/derived data, redistribution, LLM and storage

### Short answer
Under CTA (NYSE-administered) and UTP (Nasdaq-administered) policies a **Nonprofessional
Subscriber** is a natural person who receives data for personal, non-business use, in an
account in their own name, and who is not a "Securities Professional" — i.e., not registered
or qualified with the SEC, CFTC, any state securities agency, any exchange/association or
futures market, and not acting as an investment adviser (registered or not). An LLC, trust,
partnership or any entity-named account is automatically professional, as is anyone who
receives data through an organization's account or whose employment/business relationship
makes them an extension of a firm. Individuals pay about $1/month per SIP network at Level 1;
professionals pay roughly 20–45x for display and are additionally exposed to non-display and
access fees in the thousands per month. Running your own algorithm on real-time data is
conceptually "non-display use", but CTA's fee schedule expressly exempts nonprofessional users
from non-display, access and device fees — the $1 charge is the only one. Alpaca and Massive
both license individual plans for personal use only: no redistribution, no derived products
reaching third parties. Storing data for your own backtesting is personal use. Sending
real-time data to a third-party LLM API is a grey area: Nasdaq's 2025 AI policy treats
LLM/RAG distribution and model training as license-governed and potentially fee-liable for its
licensees; no CTA/UTP end-user rule found.

### Detail

**Definitions (CTA/NYSE and UTP/Nasdaq)**
- CTA Nonprofessional Subscriber Policy and NYSE Policy: natural person; personal,
  non-business use; not a Securities Professional (registered/qualified with SEC, CFTC, state
  securities agency, exchange/association, commodities/futures market; or acting as an
  investment adviser under the Advisers Act). A bank employee is not disqualified merely by
  employer. Account in a business name → professional even if used personally (the "gas
  station owner" example). Trusts and investment clubs are organizations and cannot qualify;
  an unpaid natural person associated with one can qualify individually. Retired
  professionals can qualify if CRD shows not registered, with semi-annual re-verification.
  Vendors must verify against FINRA CRD and SEC IAPD before granting the rate.
- UTP Data Policies / Nasdaq Subscriber Agreement: identical three-prong test plus a
  questionnaire — a "YES" to any disqualifying question makes the subscriber professional;
  an agreement signed in the name of a business or commercial entity is professional use;
  subcontractors/independent contractors signing in that capacity are not natural persons;
  personal use through an organization's account is professional. Nasdaq expects distributors
  to re-categorize subscribers regularly; status can only move toward professional.
- Massive's own FAQ restates: a corporation, LLC, trust, joint venture, partnership or other
  entity cannot be a Non-Professional Subscriber; "any use of Market Data for business,
  professional, or other commercial purposes is incompatible with Non-Professional status."

**Disqualifiers relevant to this project**
- Registering with any regulator (Series 7/65, IA registration, CTA/CPO) → professional.
- Trading other people's money, advising others, or being paid for signals → professional.
- Forming an LLC and putting the brokerage/data account in its name → professional (by
  entity status alone). Keep the account in the individual's name.
- Using the data to build a product others see (even a published chart or a scanner others
  access) → redistribution/commercial use; Alpaca staff explicitly cite a scanner others
  access as disallowed.

**Fee difference**
- CTA (2017 SEC filing, still the structure in effect): nonprofessional users pay only the
  $1.00/month Level 1 charge per network and "are not subject to Non-Display Use, access, or
  device fees, regardless of the type of data product they receive." Vendors may cap a
  nonprofessional's per-quote charges at $1.00.
- Nasdaq fee schedule (2025 filing): Nasdaq Level 2 nonprofessional $15/month vs professional
  $80.50 (2025) → $84 (2026) → $86 (2027). PHLX options data: nonpro $1 vs pro ~$42–45.
  UTP Level 1 and CTA Network A/B professional display rates for 2026 were not retrieved
  (UNCONFIRMED; historically in the ~$20–$45/month range per network, with professional
  non-display fees in the low thousands per month per network).
- Vendor-level: Alpaca Algo Trader Plus $99/month (personal use); Alpaca "Broker
  Professional"/business tier $99 per device/month; Broker API professional tables from $500
  to $2,000/month. Massive Business plans start at ~$1,999/month.

**Consequences of misclassification**
- Contractual attestation: "by continuing to receive the Information at a non-professional
  subscriber rate, Subscriber is affirming to Vendor and NASDAQ that Subscriber meets the
  definition." Exchanges have inspection/audit rights; the Nasdaq agreement includes recovery
  of administrative, investigatory, litigation costs and auditors'/attorneys' fees. Industry
  guides describe back-billing at professional rates, potentially for years, plus penalties.
  The vendor (Alpaca/Massive) can reclassify the account and bill professional rates;
  Massive notes a professional classification cannot be reversed by support. No criminal
  exposure found; this is contractual.

**Non-display and derived data**
- CTA definition (2014 fee amendments, CTA Non-Display Use FAQ 2016): accessing, processing
  or consuming real-time Network A/B quotation or last-sale data "for a purpose other than in
  support of a data feed recipient's display or further internal or external redistribution".
  Examples include "trading in any asset class" and "price referencing for algorithmic
  trading". Automated/algorithmic trading is the quintessential non-display use.
- But: the same filings confirm nonprofessional users are exempt from non-display fees. So an
  individual's personal algorithm is non-display in nature but carries no non-display fee or
  separate license as long as the person remains a bona fide nonprofessional. Nasdaq's
  European policy (not UTP) lists "fully automated trading" as non-display trading activity;
  the US UTP policy excerpt did not surface an equivalent end-user carve-out (UNCONFIRMED).
- Derived data (Nasdaq Global Data Agreement 2025 §1.8, mirrored in US Equities and Options
  Data Policies): information generated in whole or part from Nasdaq information that cannot
  be reverse-engineered to recreate it or serve as a reasonable substitute. Internal signals,
  indicators and model features are derived data; they only become a license issue when they
  leave the subscriber.
- Alpaca: Terms and Conditions state that selecting a paid plan means agreeing to the Nasdaq
  Global Subscriber Agreement and/or NYSE Agreement for Market Data Display Services; the
  "non-professional" definitions there are incorporated by reference. Customer Agreement: "I
  agree not to reproduce, distribute, sell or commercially exploit the market data in any
  manner without written consent from Alpaca." Alpaca support: redistribution not permitted;
  Alpaca staff (forum, ~Sept 2026): data licensed only for personal use, no commercial use,
  data or products derived from it cannot go to third parties; Alpaca is "working on
  additional licensing arrangements" for commercial use. Elite's free ATP is "only for
  personal use." No Alpaca document found that uses the term "non-display" for ATP
  (UNCONFIRMED whether Alpaca's exchange filings classify ATP users as display subscribers).
- Massive: Individual plans (Basic→Advanced) "licensed for personal and non-professional use";
  knowledge base: "your own research, your own scripts, your own trading" is covered; "the
  moment data reaches someone else ... it is redistribution." However the Market Data Terms
  of Service (PDF last updated 2024-10-09; a 2025-08-28 revision is reported) say all Market
  Data is "strictly for display use only" unless otherwise agreed, list non-display use and
  derived works among restricted activities, and require deletion of all Market Data on
  termination/suspension. This conflicts with the marketing and FAQ; a third-party reading
  suggests it could reach locally stored flat files. Get Massive's written confirmation before
  depending on a Massive archive for backtesting.

**Storage for backtesting and LLM use**
- Storing historical data locally for your own backtests is personal use under both
  vendors' FAQs; Massive's termination-deletion clause is the only identified storage risk.
- Sending data to a third-party LLM API: Nasdaq's Data AI Policy (Data News #2025-2, PDF
  `Data_AI_Policy.pdf`) clarifies that training AI models on Nasdaq information must comply
  with the governing license, open-source models are off limits without written consent,
  distribution of Nasdaq information through LLMs or RAG must be controlled by an auditable
  technical entitlement system, trained models "may be fee-liable" and third-party AI
  providers "may be required to obtain a license ... directly from Nasdaq." This is written
  for Nasdaq licensees (vendors, professional firms). For a nonprofessional end user the
  operative constraint is the vendor's personal-use/no-third-party clause; passing raw
  real-time quotes to an external model provider arguably "furnishes data to a third party",
  while passing your own derived summaries (signals, PnL, decisions) does not recreate the
  feed and fits the derived-data definition. No CTA/UTP end-user AI rule was found. Treat raw
  real-time redistribution to any external API as not permitted; derived/aggregated content
  as low risk; keep the LLM out of the real-time path entirely if possible.

### Design implications
- Keep the brokerage and data accounts in the individual's own name; do not create an LLC
  for the trading activity without accepting professional data rates (and re-papering Alpaca).
- Never share, publish, or expose raw or near-raw quotes/trades/bars outside the system:
  no public dashboards, no Discord posts of tick data, no shared scanner.
- Design the AI coding agent's inputs so it sees synthetic/sample data or heavily derived
  artifacts (metrics, logs), not live SIP data; if an LLM is used at runtime, feed it derived
  features and decisions, not raw quotes.
- Store backtest archives locally; if Massive is used, keep a policy to delete Massive data
  on termination and prefer Alpaca-sourced history for long-term archives.
- Re-answer the nonprofessional questionnaire honestly if circumstances change (registration,
  managing others' money, incorporation); budget for professional rates if any of those occur.

**Confidence:** high on definitions and disqualifiers; medium on current fee amounts; medium
on the non-display-exemption reading (based on 2017 SEC filing text, consistent with later
fee schedules); low on LLM-specific treatment (policy exists at Nasdaq only, aimed at
licensees).
**Consult a professional?** Yes if any plan involves an entity, outside capital, selling
signals, or sharing an LLM-based product; otherwise no — but confirm Massive's non-display and
storage wording in writing with Massive before relying on its archive.

### Sources
- CTA Nonprofessional Subscriber Policy: https://www.ctaplan.com/publicdocs/ctaplan/notifications/trader-update/Policy%20-%20Non-Professional%20Subscribers%20-%20CTA.pdf
- NYSE Nonprofessional Subscriber Policy: https://www.nyse.com/publicdocs/nyse/data/Policy-Non-ProfessionalSubscribers_PDP.pdf
- NYSE Market Data Vendor Guide (verification via CRD/IAPD): https://www.nyse.com/publicdocs/ctaplan/notifications/trader-update/NYSE%20Market%20Data%20Vendor%20Guide.pdf
- UTP Data Policies (Sept 2023): https://www.utpplan.com/DOC/datapolicies.pdf
- UTP Plan Subscriber Agreement: https://www.utpplan.com/DOC/subagreement.pdf
- Nasdaq US Equities and Options Data Policies: https://www.nasdaqtrader.com/content/AdministrationSupport/Policy/USEquitiesandOptionsDataPolicies.pdf
- Nasdaq guidance on non-professional usage (Data News 2007-33): https://www.nasdaqtrader.com/Tradernews.aspx?id=nva2007-033
- Nasdaq subscriber agreement (DriveWealth copy, audit/cost-recovery clause): https://legal.drivewealth.com/nasdaq-subscriber-agreement
- Nasdaq fee filing SR-NASDAQ-2024-076 (Level 2 pro/nonpro): https://www.sec.gov/files/rules/sro/nasdaq/2024/34-101839-ex5.pdf
- Nasdaq fee filing SR-NASDAQ-2026-076: https://www.sec.gov/files/rules/sro/nasdaq/2026/34-106336-ex5.pdf
- CTA non-display fee filing SR-CTA/CQ-2017-04 (nonpro exemption): https://www.sec.gov/files/rules/sro/nms/2017/34-82071.pdf
- CTA Non-Display Use FAQ (2016): https://www.ctaplan.com/publicdocs/ctaplan/notifications/trader-update/CTA%20Non%20Display%20Use%20FAQ.pdf
- CTA fee amendment (Federal Register 2017): https://www.federalregister.gov/documents/2017/11/20/2017-25027/consolidated-tape-association-notice-of-filing-and-immediate-effectiveness-of-the-twenty-second
- Nasdaq Data AI Policy: https://www.nasdaqtrader.com/content/AdministrationSupport/AgreementsData/Data_AI_Policy.pdf
- Nasdaq Data News 2025-2 (AI clarification): https://www.nasdaqtrader.com/TraderNews.aspx?id=DN2025-2
- Nasdaq Global Data Agreement (2025, derived data §1.8): https://www.nasdaq.com/docs/2025/11/18/Nasdaq-Global-Data-Agreement-Form_3.pdf
- Alpaca Terms and Conditions (plan → exchange agreements): https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf
- Alpaca redistribution support page: https://alpaca.markets/support/redistribute-alpaca-api
- Alpaca forum "Use SIP data feed for display" (staff: personal use only): https://forum.alpaca.markets/t/use-sip-data-feed-for-display/19641
- Massive: Am I a professional or non-professional subscriber?: https://massive.com/knowledge-base/article/am-i-a-professional-or-non-professional-subscriber
- Massive: pro/non-pro classifications for stock data: https://massive.com/knowledge-base/article/what-are-pro-and-non-pro-classifications-for-massives-stock-data
- Massive: redistribution: https://massive.com/knowledge-base/article/how-can-i-redistribute-massives-market-data
- Massive Market Data Terms of Service: https://massive.com/legal/market-data-terms-of-service and https://massive.com/terms/market_data_terms.pdf
- Third-party reading of Massive's 2025 terms: https://github.com/mengrenman/Polygon.io-data-ingestion-pipeline/pull/26
- Industry explainer on audits/back fees: https://godeldiscount.com/blog/exchange-fees-market-data-subscriptions

---

## 3. Alpaca Algo Trader Plus and Massive plan terms

### Short answer
Algo Trader Plus ($99/month): full SIP coverage for US equities (plus OPRA options), unlimited
WebSocket symbol subscriptions, no 15-minute restriction on recent history, 10,000 historical
REST calls/min, history back to 2016 (same on Basic). Weakness: delisted/inactive symbols
frequently return no bars, no historical-assets endpoint, OTC never covered, bars forward-fill
after a stock moves to OTC. Massive: only the Advanced plan ($199/month) is real-time for US
stocks (Starter $29 and Developer $79 are 15-minute delayed); Advanced has tick trades/quotes
back to 2003, explicitly survivorship-bias-free with delisted tickers queryable via
`tickers?active=false`, `delisted_utc`, and a point-in-time tickers API; WebSocket is one
connection per asset cluster; REST "unlimited" on paid plans subject to fair use. Neither
vendor prohibits automated trading on individual plans; both restrict to personal use.

### Detail

**Alpaca Algo Trader Plus**
- Price $99/month; Basic free (IEX real-time only, 30 WS symbols, latest-15-minutes of
  historical data blocked, 200 hist calls/min). ATP: all US exchanges (SIP), unlimited WS
  symbols for equities, 1,000 option quote WS subscriptions, 10,000 hist calls/min, no recent
  history restriction. Historical depth: docs say data from 2016 on both plans.
- WebSocket concurrent connections: Basic 1 for stocks; ATP cap UNCONFIRMED (excess returns
  code 406).
- Delisted/inactive: forum reports that symbols on the inactive list return no historical
  data even for active dates; Alpaca staff: "we do not have an endpoint for historical assets"
  (an `asof` variant was planned); `asof` parameter on historical endpoints maps symbol
  changes but has had errors (reused ticker "Q" mixed two companies). Data stops when a stock
  leaves an exchange; later daily bars may be forward-filled. Delisted assets may have numeric
  or suffixed symbols in the assets list.
- Terms: personal use only; no redistribution; no "non-display" terminology found; Alpaca
  actively markets the plan to algorithmic traders, so automated use is the intended use.
- Alpaca has been subject to third-party market data outages (e.g., unresolved "3rd Party
  Outage affecting Market Data" posted 2026-10-15).

**Massive (formerly Polygon.io; rebrand 2025-10-30; polygon.io redirects; legacy API host
still works)**
- Stocks plans: Basic $0 (5 calls/min, EOD, 2 years); Starter $29 (15-min delayed intraday,
  unlimited calls, WebSocket, 5 years per FAQ — one page says 10); Developer $79 (delayed,
  10 years, trades included, quotes not included); Advanced $199 (real-time trades, quotes
  and bars from every US venue, tick history to 2003, "20+ years"); Business from ~$1,999.
  Plan tables conflict between pages — read the live pricing page before purchase.
- Rate limits: paid plans "unlimited" REST subject to soft fair-use limits; WebSocket one
  simultaneous connection per cluster (stocks/options/forex/crypto); a second connection to
  the same cluster drops the first. Per-tier WebSocket concurrency figures beyond this are
  third-party and UNCONFIRMED.
- Delisted tickers: covered; "delisted tickers keep their full history"; `tickers`
  endpoint returns active only by default — pass `active=false`; `delisted_utc` field; last
  bar date can differ from `delisted_utc` (Twitter example: last bar 2022-10-27, delisted
  2022-10-31); renamed companies keep separate histories under each symbol (no stitching);
  point-in-time tickers API for as-of queries; reference data including delisted tickers is
  on every plan. Flat files (S3, CSV/Parquet daily drops) for bulk/backtest loads.
- Terms: individual plans personal/non-professional; redistribution prohibited; Market Data
  Terms contain display-only, non-display and derived-works restrictions plus a
  delete-on-termination clause (see Q2). No automated-trading prohibition; FAQ says "your own
  scripts, your own trading" is covered.

### Design implications
- Primary real-time feed: Alpaca ATP SIP stream (one WS connection, unlimited symbols);
  fallback real-time requires Massive Advanced ($199), not Starter/Developer — budget $298/month
  for true redundancy, or accept delayed Massive data as a reference-only fallback.
- Build the universe and backtests on Massive (Advanced or flat files) for survivorship-free
  history; use Alpaca history for recent, execution-aligned data. Reconcile symbol mappings
  across vendors (Massive does not stitch renames; Alpaca `asof` does, imperfectly).
- Maintain a single WS connection per vendor cluster with reconnect logic that assumes any
  second connection kills the first.
- Keep separate REST budgets: Alpaca data 10,000/min, Alpaca trading 200/min, Massive
  fair-use.
- Store Massive-derived archives with a documented deletion policy; treat Alpaca as the
  long-term archive source where possible.

**Confidence:** high on Alpaca plan features and Massive delisted coverage; medium on Massive
plan tiers (pages conflict); low on ATP WS connection cap.
**Consult a professional?** No.

### Sources
- About Market Data API: https://docs.alpaca.markets/us/docs/about-market-data-api
- Market Data FAQ: https://docs.alpaca.markets/us/docs/market-data-faq
- Real-time stock data: https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data
- Forum: historical data for inactive stocks: https://forum.alpaca.markets/t/get-historical-data-for-inactive-stocks/10097
- Forum: delisted tickers: https://forum.alpaca.markets/t/delisted-tickers/18227
- Forum: ABAT history: https://forum.alpaca.markets/t/cant-see-full-history-on-abat/13070
- Forum: symbol "Q" mapping bug: https://forum.alpaca.markets/t/fixing-data-historical-bars-of-symbol-q-are-comprised-of-two-different-stocks/18184
- Alpaca rate limits (third-party summary): https://apis.io/rate-limits/alpaca-markets/alpaca-markets-rate-limits/
- Massive pricing: https://massive.com/pricing
- Massive stocks: https://massive.com/stocks
- Massive REST stocks overview: https://massive.com/docs/rest/stocks/overview
- Massive All Tickers endpoint: https://massive.com/docs/rest/stocks/tickers/all-tickers
- Massive: What does Massive do with delisted tickers?: https://massive.com/knowledge-base/article/what-does-massive-do-with-delisted-tickers
- Massive: ticker changes and acquisitions: https://massive.com/knowledge-base/article/how-does-massive-handle-ticker-changes-and-acquisitions
- Massive: Point-in-Time Tickers API: https://massive.com/blog/new-point-in-time-tickers-api
- Massive flat files (day aggregates): https://massive.com/docs/flat-files/indices/day-aggregates.md
- Massive Python client (WS one connection per cluster): https://polygon.readthedocs.io/en/latest/Async-Streaming.html
- Polygon/Massive rate limits (third-party): https://apis.io/rate-limits/polygon/polygon-rate-limits/
- Pricing review 2026 (third-party): https://qveris.ai/guides/polygon-pricing-optimized

---

## 4. Regulation T and FINRA Rule 4210 after Regulatory Notice 26-10

### Short answer
Effective 2026-06-04 (phase-in to 2027-10-20), FINRA Rule 4210 no longer contains pattern-day-
trader concepts or the $25,000 minimum. The $2,000 minimum equity for a margin account's
initial transaction (Rule 4210(b)) is untouched. New paragraph (d)(2) requires firms to compute
an "intraday margin level" (IML — cash the customer could withdraw while still meeting
maintenance margin, or must deposit to meet it), identify "IML-reducing transactions"
(purchases not covering a short, short sales, option exercise/assignment/expiration,
withdrawals), and compute the "intraday margin deficit" (largest negative IML). Deficits must be
met "as promptly as possible" via net deposits or IML-increasing activity; a customer with a
practice of failing to meet deficits is restricted for 90 calendar days after the fifth
business day from opening/increasing short positions or debit balances. FINRA did publish the
interpretive follow-up: Regulatory Notice 26-11 (2026-05-19) with new interpretations
including 4210(d)(2)(D)/01 "Practice of Failing to Satisfy Intraday Margin Deficits as
Promptly as Possible." A long-only margin account whose gross exposure never exceeds its cash
cannot generate a negative IML (requirement ≤ market value ≤ equity), so it cannot incur an
intraday or maintenance margin call except through edge cases that drive cash negative (fee
debits, over-fills, bugs). The Reg T 90-day freeze (12 CFR 220.8(c)) and free-riding/good-faith
violations are cash-account rules; in a margin account the relevant Reg T provision is the
payment period (settlement + 2 business days = T+3 under T+1) with mandatory liquidation
absent an extension, and Alpaca's float coverage means reusing unsettled proceeds is permitted.

### Detail
- SEC approved SR-FINRA-2025-017 on 2026-04-14/15 (Release 34-105226) by accelerated approval.
  FINRA RN 26-10 published 2026-04-20; effective 2026-06-04; phase-in period ends 2027-10-20
  (firms may continue legacy practices during phase-in — Alpaca chose to switch on day one).
- Removed: pattern day trader definition, 4-trades-in-5-days test, $25,000 minimum,
  day-trading buying power (4x), day-trade margin calls, and all related interpretations.
- Rule 4210(d)(2): applies to customer margin accounts on days with an IML-reducing
  transaction; good-faith accounts excluded; portfolio margin accounts get separate intraday
  monitoring via (g)(1)(J),(K). If a member cannot establish sequence of same-day activity it
  must assume the order producing the highest deficit. Firms may choose real-time monitoring
  that blocks IML-reducing orders, or an end-of-day computation with a margin call. A deficit
  is satisfied when, by the end of a subsequent day, net deposits or IML-increasing activity
  cover it; the deficit remains outstanding until satisfied or the close of the 15th business
  day. "Practice of failing" → written procedures to restrict for 90 calendar days after the
  fifth business day or until satisfied; closing a short is still permitted.
- RN 26-11 (2026-05-19): updated Rule 4210 interpretations effective 2026-06-04, deleting
  day-trading interpretations and adding ones on acceptable methods for computing an intraday
  margin deficit, treatment of same-day deposits/withdrawals, and the "practice of failing"
  standard. FINRA also published an investor-insights page "Understanding the New Intraday
  Margin Requirements." Exact interpretive wording was not retrievable (UNCONFIRMED details).
- $2,000 minimum: Rule 4210(b) (initial margin: Reg T requirement or $2,000, whichever
  greater, except that cash need not exceed the cost of the security) is not referenced in
  any amendment summary; Firstrade's launch release calls $2,000 "the standard margin account
  minimum" still applying. Alpaca treats < $2,000 equity as multiplier-1 "limited margin."
  Note: nothing requires an individual to maintain $2,000 to hold a margin-type account at
  Alpaca; the $2,000 governs whether margin credit can be extended for a new purchase.
- Can a never-leveraged account incur a call? Maintenance requirement for longs is at most
  100% of market value (Alpaca's house rate for < $2.50 stocks; FINRA minimum 25%). If open
  notional ≤ cash at entry and cash is never negative, then equity = cash + MV ≥ MV ≥
  requirement, so IML ≥ 0 and no deficit or maintenance call arises, regardless of price moves
  (a drop lowers MV and requirement together). Residual paths to a call: (i) regulatory fee
  debits settled EOD against zero cash; (ii) partial fills or duplicate orders exceeding
  intended size; (iii) Alpaca raising a house requirement above 100% (not seen); (iv) a
  position becoming non-marginable mid-day (requirement rises to 100%, still ≤ MV). Alpaca's
  de minimis ($1,000 / 5%) further absorbs (i). Reg T initial margin (50%) is satisfied by any
  100%-cash purchase.
- Reg T: § 220.8(c) imposes the 90-day withdrawal of the deferred-payment privilege in a
  **cash account** when a security is sold before being paid for (free-riding); the
  good-faith-violation concept is likewise a cash-account construct (FINRA investor guidance).
  § 220.4 margin account: payment for a purchase is due within one "payment period"
  (§ 220.2: standard settlement cycle + 2 business days → T+3 under T+1 since 2024-05-28);
  if not received the broker must promptly cancel or liquidate (§ 220.4(d)) unless it obtains
  an extension (§ 220.4(c)(3)); FINRA RN 23-15 confirms the T+4 → T+3 shift. Because every
  Alpaca account is a margin account and Alpaca covers the settlement float, the
  cash-account 90-day freeze does not apply to this setup. Full text of § 220.4 was not
  retrieved (UNCONFIRMED on fine print).

### Design implications
- The system's hard invariant should be "open notional ≤ settled-plus-unsettled cash minus a
  fee buffer," computed from `cash` and position marks, independent of broker buying power.
- Do not rely on the de minimis threshold; treat any `intraday margin call` or negative
  `cash` as a halt condition with automatic position flattening.
- No $25,000 floor and no day-trade counting are needed in the code; remove any PDT logic.
  Keep the account above $2,000 anyway so Alpaca does not downgrade capabilities.
- Log order sequencing precisely (timestamps, client order IDs); FINRA's worst-case
  sequencing assumption means ambiguous same-day activity is resolved against the customer.
- Because Alpaca blocks IML-reducing orders pre-trade, expect order rejections rather than
  calls as the first symptom of any margin problem; handle rejection codes gracefully.

**Confidence:** high on the rule's existence, dates, structure and RN 26-11; medium-high on
the "no call if never leveraged" analysis (follows from definitions; Alpaca may impose house
rules); medium on Reg T margin-account mechanics (text not read directly).
**Consult a professional?** Not required for an individual; a short paid consult with a
securities compliance attorney is cheap insurance if the account will ever hold overnight,
short, or use options.

### Sources
- FINRA Rule 4210: https://www.finra.org/rules-guidance/rulebooks/finra-rules/4210
- FINRA Regulatory Notice 26-10: https://www.finra.org/rules-guidance/notices/26-10 (PDF: https://www.finra.org/sites/default/files/2026-04/Regulatory-Notice-26-10.pdf ; Attachment A rule text: https://www.finra.org/sites/default/files/2026-04/Regulatory-Notice-26-10-Attachment-A.pdf)
- FINRA Regulatory Notice 26-11 (interpretations): https://www.finra.org/rules-guidance/notices/26-11
- Interpretations of Rule 4210 valid from 2026-06-04: https://www.finra.org/rules-guidance/guidance/interps-4210-202606
- FINRA investor insight: https://www.finra.org/investors/insights/intraday-margin-requirements
- SEC approval order 34-105226: https://www.sec.gov/files/rules/sro/finra/2026/34-105226.pdf
- SEC notice 34-104572 / Exhibit 5: https://www.sec.gov/files/rules/sro/finra/2026/34-104572-ex5.pdf
- Federal Register notice (2026-01-14): https://www.federalregister.gov/documents/2026/01/14/2026-00519/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-of-a
- WilmerHale alert: https://www.wilmerhale.com/en/insights/client-alerts/20260423-sec-approves-amendments-to-finra-rule-4210-replacing-day-trading-margin-requirements-with-a-modernized-intraday-margin-standard
- King & Spalding alert: https://www.kslaw.com/insights/articles/finra-adopts-sweeping-changes-to-margin-requirements-for-day-trading
- Wilson Sonsini alert: https://www.wsgr.com/en/insights/finra-adopts-new-intraday-margin-requirements.html
- ACA Group summary: https://www.acaglobal.com/industry-insights/finra-ends-the-pattern-day-trader-rule/
- Firstrade release ($2,000 minimum): https://www.firstrade.com/press/20260604
- Reg T § 220.8 (eCFR): https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-220/section-220.8
- Reg T § 220.8 (LII): https://www.law.cornell.edu/cfr/text/12/220.8
- FINRA RN 23-15 (Reg T payment period under T+1): https://www.finra.org/rules-guidance/notices/23-15
- FINRA RN 17-12 (payment period definition): https://www.finra.org/rules-guidance/notices/17-12
- FINRA: Frequent intraday trading / cash account free-riding: https://www.finra.org/investors/insights/frequent-intraday-trading
- SEC investor bulletin, trading in cash accounts: https://www.sec.gov/investor/alerts/cashaccounts.pdf

---

## 5. Brokerage protections and outage risk

### Short answer
Alpaca Securities LLC (dba Alpaca Clearing) is a self-clearing, carrying broker-dealer (FINRA
and SIPC member; Nasdaq exchange member since Oct 2025), so there is no separate clearing firm
to evaluate. SIPC covers up to $500,000 per customer per capacity, including $250,000 for
cash, on a net-equity basis (margin debt is deducted); it covers missing assets when a member
fails, not market losses, bad advice, futures, unregistered contracts, or bank-sweep balances
(those get pass-through FDIC). Alpaca carries excess-SIPC via Lloyd's: $75M securities and $75M
cash per customer, $250M aggregate. Alpaca's BCP summary promises to resume trading as soon as
possible and points to status.alpaca.markets and social media for updates; it does not
document what happens to open orders during an API outage (UNCONFIRMED). The status record for
2025–2026 shows recurring short degradations and at least two multi-hour Trading API incidents
in August 2026, plus a two-week paper-crypto fill failure in Nov 2025 that never appeared on
the status page.

### Detail
- SIPC: $500,000 limit including $250,000 cash; "net equity" = what the firm owes you minus
  what you owe it (margin loan deducted); separate legal capacities may be covered separately;
  protection requires firm failure and a filed claim; not covered: market losses, damage
  claims (bad advice), commodity futures, unregistered investment contracts/LPs, assets at
  non-member firms. Alpaca FDIC Bank Sweep balances are outside SIPC (pass-through FDIC
  intended).
- Alpaca clearing: self-clearing since it became a carrying broker (blog "Alpaca Securities
  LLC as a Carrying Broker Dealer"); Nasdaq membership announced 2025-10-15 allowing direct
  order-book connectivity. Excess SIPC expanded to $75M/$75M/$250M aggregate (prior
  $30M securities / $1M cash / $150M aggregate); expansion reported Feb 2026.
- Outage handling: BCP summary (files.alpaca.markets) — aims to continue or resume operations
  ASAP; customers directed to the Alpaca Status page; if primary channels fail, contact
  details published via alternative site/social media. No published phone trading desk for
  retail API customers found (UNCONFIRMED). Nothing found on whether resting orders at
  exchanges/wholesalers remain live when Alpaca's API is unreachable (general industry
  practice: orders already accepted stay working at the venue; the customer just cannot see or
  cancel them).
- Status history found (mostly via aggregators; Alpaca's own history page not retrievable):
  - 2026-10-15: "Unresolved incident: 3rd Party Outage affecting Market Data" (status page).
  - 2026-08-12: Live Trading API performance degradation ~6h; "incorrect position updates
    after sell orders" ~1.5h plus ~5.75h investigation.
  - 2026-08-04: order status discrepancies ~2h20m.
  - 2026-07: forum reports of paper-account positions wiped / paper trade issues.
  - 2026-05: minor Trading API disruption; 2026-03-31: account-information endpoints
    timing out; May–July 2026 scheduled maintenance windows up to ~3.5h.
  - 2025-12: Cloudflare outage hit dashboard/docs; APIs reportedly unaffected.
  - 2025-11-05 to ~11-17: paper crypto orders not filling / positions vanished; staff
    acknowledged; status page showed nothing.
  - 2025-03: paper crypto orders halting after 8 AM.
  Official 2025 incident list: UNCONFIRMED (not retrievable by search).

### Design implications
- Assume the API can go dark mid-session: on loss of order/position stream or repeated
  5xx/timeouts, stop placing new orders, attempt cancel-all, and alert the human with the
  status-page link; do not assume cancels succeeded until confirmed.
- Reconcile positions after any incident: the Aug-2026 "incorrect position updates after
  sells" incident means position state from the API can be wrong; cross-check fills from
  `/v2/account/activities` before resuming.
- Keep cash at Alpaca within SIPC comfort (the excess policy helps but is aggregate-capped);
  this is a modest account so SIPC is adequate, but do not treat the sweep as SIPC-protected.
- Treat paper trading as a weaker reliability signal than live (paper-only incidents are
  common and under-reported).

**Confidence:** high on SIPC and clearing structure; medium on outage history (third-party
aggregators); low on open-order handling during outages.
**Consult a professional?** No.

### Sources
- Customer asset protection at Alpaca: https://alpaca.markets/learn/customer-asset-protection-at-alpaca
- Alpaca as carrying/self-clearing broker: https://alpaca.markets/blog/alpaca-securities-llc-as-a-carrying-broker-dealer-and-clearing-for-others-explained/
- Excess SIPC expansion: https://alpaca.markets/blog/alpaca-clearing-expands-excess-sipc-coverage-strengthening-commitment-towards-enhanced-protection/
- Nasdaq membership (Oct 2025): https://www.businesswire.com/news/home/20251015470123/en/Alpaca-Secures-Nasdaq-Exchange-Membership-Advancing-Full-Stack-Brokerage-Infrastructure
- SIPC: What is SIPC?: https://www.sipc.org/for-investors/introduction
- SIPC claims process (net equity): https://www.sipc.org/cases-and-claims/how-the-claims-process-works
- SIPC brochure: https://www.sipc.org/media/brochures/HowSIPCProtectsYou-English-Web.pdf
- Alpaca BCP summary: https://files.alpaca.markets/disclosures/alpaca_business_continuity_plan_summary.pdf
- Alpaca status page: https://status.alpaca.markets/
- StatusGator Alpaca: https://statusgator.com/services/alpaca
- StatusField Alpaca: https://statusfield.com/services/alpaca
- Pingoru Alpaca incidents: https://pingoru.io/providers/alpaca/incidents/71930
- Forum: paper crypto trades broken (Nov 2025): https://forum.alpaca.markets/t/paper-crypto-trades-broken/18126
- Forum: paper positions wiped (Jul 2026): https://forum.alpaca.markets/t/alpaca-paper-account-positions-wiped/19225

---

## 6. Penny stock rules (SEC Rules 3a51-1 and 15g-1 to 15g-9)

### Short answer
Exchange-listed stocks priced under $5 are generally **not** "penny stocks": Rule 3a51-1(a)
excludes NMS stocks listed on a national securities exchange that meets specified listing
standards (NYSE, Nasdaq, NYSE American/Arca etc.), and 3a51-1(e) separately excludes
exchange-registered securities when the transaction is effected on the exchange. The
broker-dealer obligations in Rules 15g-2 (Schedule 15G risk disclosure document with signed
acknowledgment and a two-business-day cooling-off) and 15g-9 (written suitability
determination and signed agreement, with exemptions for established customers and accredited
investors) attach only to true penny stocks, i.e., mainly OTC-quoted equities under $5. Alpaca
does not offer OTC trading (apart from a few ADRs), so these rules are practically moot for
this system unless a held stock is delisted to OTC, in which case it becomes sell-only.

### Detail
- Rule 3a51-1 defines "penny stock" as any equity security except: (a) an NMS stock listed on
  an exchange that has been continuously registered since 1992-04-20 with listing standards
  at least as strict as those of 2004-01-08, or that meets specified initial listing criteria
  (including $4 minimum bid, net tangible assets/market value/revenue tests); (b) securities
  of registered investment companies; (c) OCC-issued options; (d) securities priced $5 or
  more (transaction price excluding commissions, or inside bid when not in a transaction);
  (e) securities registered on a national securities exchange, provided the transaction is
  effected on or through the exchange's facilities or is part of a distribution — note that
  securities excluded only by (e) remain penny stocks for Exchange Act §15(b)(6) penny-stock
  bar purposes; (f)/(g) issuer net tangible assets ($2M / $5M) or average revenue ($6M) tests.
  A Nasdaq Capital Market stock trading at $1–$5 is covered by (a) regardless of whether the
  particular execution is on-exchange or at a wholesaler. Current eCFR cross-references were
  renumbered (§242.600(b)(65) for NMS stock) — confirm the live text.
- Rule 15g-1 exemptions (summary from secondary sources, UNCONFIRMED in detail): e.g.,
  broker-dealers whose penny-stock commissions are under 5% of total commissions; transactions
  with institutional accredited investors; issuer transactions; unsolicited transactions where
  the broker does not recommend.
- Rule 15g-2: unlawful to effect a penny-stock transaction unless the broker-dealer first
  distributes the Schedule 15G risk disclosure document and receives a signed, dated
  acknowledgment; 2005 amendments added an explicit cooling-off period (two business days)
  when the document is delivered, and updated Schedule 15G.
- Rule 15g-9: broker-dealer must approve the account for penny-stock transactions by
  obtaining information about the customer's financial situation, investment experience and
  objectives, reasonably determining penny stocks are suitable, delivering a written statement
  of that determination, and receiving a signed written agreement to the specific transaction;
  no sale may occur less than two business days after sending the agreement. Exemptions:
  established customers (account with a transaction or deposit more than one year earlier, or
  three prior penny-stock purchases on different days), accredited investors, and the 15g-1
  exempt transactions.
- Rules 15g-3 to 15g-6: disclosure of quotations, compensation of the broker-dealer and
  associated persons, and monthly account statements for penny stocks; 15g-8 restricts sales
  of escrowed penny stocks.
- Alpaca: "if it trades on a US exchange you can trade it on Alpaca"; OTC not supported
  except limited ADRs; Alpaca market data covers exchange-listed only. No Alpaca penny-stock
  disclosure document was found, consistent with Alpaca not transacting in penny stocks.

### Design implications
- Universe filter: exchange-listed (NYSE, Nasdaq, NYSE American, Arca, Cboe BZX) with
  `tradable=true`; that alone keeps the system out of the penny-stock regime.
- Handle the delisting path: if a holding is halted or delisted intraday, the position may
  only be sellable (if at all) and may lose data coverage; make the end-of-day flatten
  routine robust to untradable assets and alert the human.
- Nothing to sign or acknowledge for $1–$5 listed stocks; no suitability paperwork expected.

**Confidence:** high on the definition and exclusions; medium on 15g-1 exemption details and
current Schedule 15G text.
**Consult a professional?** No for listed stocks; yes only if OTC trading is ever added.

### Sources
- 17 CFR 240.3a51-1 (LII): https://www.law.cornell.edu/cfr/text/17/240.3a51-1
- 17 CFR 240.15g-9 (LII): https://www.law.cornell.edu/cfr/text/17/240.15g-9
- SEC release 34-51983 (2005 penny stock rule amendments, cooling-off): https://www.sec.gov/files/rules/final/34-51983fr.pdf
- SEC no-action letter on 3a51-1(e) exchange-transaction condition: https://www.sec.gov/divisions/marketreg/mr-noaction/bion031803.htm
- SEC proposed rule 34-49037 (penny stock definition background): https://www.sec.gov/file/proposed-rule-release-no-34-49037
- Penny stock rules overview (Securities Lawyer 101): https://www.securitieslawyer101.com/?p=40375
- Penny stock rules and broker-dealers (lawcast): https://lawcast.com/2014/11/04/penny-stock-rules/
- Alpaca forum: stocks offered by Alpaca: https://forum.alpaca.markets/t/stocks-offered-by-alpaca/7857

---

## Items that could not be confirmed (consolidated)
1. Whether Alpaca's current onboarding includes a distinct API/algorithmic-trading
   acknowledgment beyond the Customer Agreement's automated-systems clause.
2. Whether `max_margin_multiplier="1"` disables all credit extension, and whether a
   multiplier-1 account can receive an intraday margin call (Alpaca's "Non-Leverage Margin
   Accounts" page exists but its text was not readable).
3. Exact semantics (percent vs ratio) of `margin_requirement_long` /
   `maintenance_margin_requirement` on `/v2/assets`.
4. Algo Trader Plus concurrent WebSocket connection cap.
5. Current 2026 UTP Level 1 and CTA Network A/B professional display and non-display fee
   amounts.
6. Whether Alpaca's exchange filings classify ATP individual users as display subscribers,
   and any Alpaca "non-display" wording.
7. Massive's 2025-08-28 Market Data Terms text and whether non-display/derived-works
   restrictions apply to Advanced individual plans as marketed.
8. Exact interpretive text in RN 26-11 (practice-of-failing standard; computation methods).
9. Full text of Reg T § 220.4 margin-account payment/liquidation provisions (relied on
   FINRA notices).
10. Alpaca's official 2025 incident history and open-order handling during API outages.
11. Current Schedule 15G text and 15g-1 exemption details.
