# R3 — Tax, recordkeeping and OTC-market constraints for a personal intraday trading system

Research date: 2026-10-16. Scope: one US individual, own money only, long-only, listed US stocks priced $1–$5, intraday, possibly hundreds of trades a month, full order/fill journal. OTC a possible later extension.

Method: web search only (fetch blocked). Primary sources (IRS, SEC, FINRA, OTC Markets, Federal Register) were preferred where search excerpts surfaced them; otherwise reputable CPA/law-firm commentary. Anything I could not confirm from a primary source is marked **UNCONFIRMED**. Nothing here is tax or legal advice.

---

## 1. Federal tax treatment of frequent intraday trading by an individual

### Short answer
Every intraday round trip is a short-term capital gain or loss taxed at ordinary rates (10%–37% for 2026). The wash-sale rule (IRC §1091) is the dominant compliance headache: trading the same ticker repeatedly within 30 days generates a chain of disallowed losses that are deferred, not lost, and they resolve only when a position is closed and not re-entered for 31 days — which matters at year end. The broker's 1099-B tracks wash sales only per account and per identical CUSIP; the taxpayer is responsible for the full rule. Thousands of trades can be reported on Form 8949 by summary with an attached statement. Trading profits create an estimated-tax obligation (safe harbors: 90% of current-year tax or 100%/110% of prior-year tax). NIIT (3.8%) applies above $200k/$250k MAGI. State treatment varies; a few states (notably NJ) do not allow capital-loss carryforwards at all.

### Detail

**Rates (tax year 2026, Rev. Proc. 2025-32).** Short-term gains (held ≤ 1 year — every intraday trade) are ordinary income. 2026 brackets per trade-press reporting of Rev. Proc. 2025-32: single 10% to $12,400; 12% to $50,400; 22% to $105,700; 24% to $201,775; 32% to $256,225; 35% to $640,600; 37% above. MFJ: 10% to $24,800; 12% to $100,800; 22% to $211,400; 24% to $403,550; 32% to $512,450; 35% to $768,700; 37% above. Standard deduction $16,100 single / $32,200 MFJ. The 0/15/20% preferential rates never apply to this system's gains. OBBBA (July 2025) made the TCJA rate structure permanent, so no scheduled rate reversion in 2026. (Secondary sites disagreed on a couple of lower-bracket cutoffs by ~$25; verify against the Rev. Proc. itself before hardcoding.)

**Wash-sale rule, IRC §1091.** A loss on a sale is disallowed if substantially identical stock is acquired within 30 days before or after the sale (a 61-day window including the sale date). The disallowed loss is added to the basis of the replacement shares and the holding period carries over, so the loss is deferred rather than destroyed. For an intraday system trading the same ticker many times a month:
- Nearly every losing trade in a ticker will be a wash sale if the ticker is re-entered within 30 days, and the deferred loss migrates into the basis of the next lot, which (if also sold at a loss and re-bought) migrates again. Within a year the chain nets out: when the final lot in the chain is sold and no replacement is bought within 30 days, the whole accumulated deferred loss is recognized. Practitioner sources describe pattern day traders accumulating large nominal wash-sale adjustments that net to zero by year end as long as the chain is broken.
- The year-end problem: if a December loss is washed by a purchase in late December or January (within 30 days), the loss is deferred into the next tax year, inflating the current year's taxable gain ("phantom income"). Green Trader Tax's rule of thumb (as reported): a loss deferred from November to December is harmless; a loss deferred from December to January is not. The standard fix is to be flat in every ticker that has an open wash chain by roughly December 20 and not re-enter it for 31 days (into late January), so no wash-sale bridge crosses the year boundary. The alternative fix is the §475(f) election (see §2), which removes wash-sale treatment entirely for trading positions.
- Replacement purchases in an IRA permanently forfeit the loss (Rev. Rul. 2008-5); the rule also reaches a spouse's accounts. Not relevant for a single taxable account unless the user also holds the same tickers in an IRA.

**Broker 1099-B vs. taxpayer obligation.** Under Treas. Reg. §1.6045-1 brokers report wash sales only for identical securities (same CUSIP) within the same account (KPMG, Marcum). The taxpayer must apply the full "substantially identical" test across all accounts including IRAs and across different CUSIPs. For a single-account system trading common stock by CUSIP, the broker's wash-sale accounting should match the taxpayer's in substance, but broker lot-matching and the order of adjustments can differ from an independent computation; discrepancies are reconciled on Form 8949 with code W and an adjustment amount. Boxes: Box A (basis reported, covered) sales with no adjustments can go directly on Schedule D line 1a; anything with a code W adjustment must appear on Form 8949 (or an attached statement).

**Form 8949 / Schedule D with thousands of trades.** The Form 8949 instructions allow two exceptions to line-by-line reporting. Exception 1: Box A (or D) transactions with basis reported to the IRS and no adjustments may be totaled directly on Schedule D line 1a/8a. Exception 2: instead of listing every transaction on Form 8949, attach a statement containing all the same information as Form 8949 Parts I/II in a similar format (description, date acquired, date sold, proceeds, basis, code, adjustment, gain/loss), enter the totals on a single Form 8949 line, and write "see attached statement." When e-filing, the statement is attached as a PDF or mailed with Form 8453 within 3 business days of e-file acceptance (software-vendor guidance; verify against current Form 8453 instructions). Because wash-sale-adjusted trades carry code W, a frequent trader will almost never qualify for Exception 1 alone; expect to use Exception 2 with a broker-generated or journal-generated statement. A trader with a §475(f) election instead reports on Form 4797 Part II with an attached transaction statement ("Trader—see attached", Form 4797 instructions).

**Estimated taxes.** Trading income has no withholding. Underpayment penalty (Form 2210) is avoided if payments by each quarterly due date (Apr 15, Jun 15, Sep 15, Jan 15) reach 90% of the current year's tax or 100% of the prior year's tax (110% if prior-year AGI > $150,000 / $75,000 MFS), or if the balance due is under $1,000. Each quarter is tested separately. For lumpy trading income the annualized income installment method (Form 2210 Schedule AI) can reduce penalties. The prior-year safe harbor is the simplest rule for a system whose P&L is unknown in advance.

**Net investment income tax.** 3.8% on the lesser of net investment income or MAGI above $200,000 (single) / $250,000 (MFJ) / $125,000 (MFS), thresholds not indexed. Gains from trading are NII for an investor, and under Treas. Reg. §1.1411-5 income from "a trade or business of trading in financial instruments or commodities" is NII even for a qualifying trader, so trader tax status does not avoid NIIT. A §475 trader's ordinary losses can offset other NII; an investor's capital losses are limited to $3,000 for NII purposes too.

**Capital loss limit.** Without §475, net capital losses offset only $3,000 of ordinary income per year; the rest carries forward indefinitely (federal).

**State tax (general).** Most states tax capital gains as ordinary income at their normal rates with no preferential long-term rate (irrelevant here since all gains are short-term). Nine states have no broad-based individual income tax (AK, FL, NV, NH, SD, TN, TX, WY, WA — WA has a 7% capital-gains excise above ~$270k that excludes most ordinary stock gains only if... UNCONFIRMED detail; check WA if relevant). Important traps: New Jersey taxes gains as ordinary income, allows capital losses only against capital gains in the same year, and allows **no carryforward or carryback** of a net capital loss. Pennsylvania similarly taxes by class of income with no cross-class netting and, per my understanding, no individual loss carryforward (one marketing source claimed PA allows indefinite carryforward — **conflict, UNCONFIRMED**; check PA-40 Schedule D instructions). California conforms to a federal §475(f) election automatically (Cal. R&TC §17570) and does not allow a separate state election. State estimated-tax safe harbors differ from federal. The user's state of residence drives all of this.

### Design implications for this system
- Tax lot engine: compute realized P&L per lot with FIFO (or specific identification if the broker supports it), and implement §1091 wash-sale adjustments independently (61-day window, basis roll-forward, holding-period carryover) so the journal can be reconciled against the broker's 1099-B each January.
- Year-end "flatten" rule: a configurable blackout that forces all tickers with an open wash chain to be flat by a date in mid/late December and blocks re-entry in those tickers for 31 days. Without §475(f), this is the single most important tax control in the system.
- Report generator: emit a Form 8949-format CSV/PDF (Exception 2 statement) and totals by box (A/B) and by code W, plus a Form 4797-format variant for the §475 case.
- Quarterly estimated-tax reminder with running YTD realized P&L and both safe-harbor targets (user enters prior-year tax); surface the annualized-method alternative.
- Record state of residence as a configuration item; flag NJ/PA-style no-carryforward states because they change the economics of a losing year.
- Keep every trade's exact timestamps: wash-sale windows and "same day" determinations depend on trade date, not settlement date.

Confidence: **high** on rates, wash-sale mechanics, 1099-B scope, 8949 exceptions, estimated-tax safe harbors, NIIT; **medium** on exact 2026 bracket cutoffs (secondary reporting) and on state specifics.
Consult a professional? **Yes** — at minimum a CPA for the first tax year, and the year-end wash-sale strategy.

### Sources
- IRS Topic 429, Traders in securities: https://www.irs.gov/taxtopics/tc429
- IRS Instructions for Form 4797 (2025): https://www.irs.gov/instructions/i4797
- IRS Schedule D instructions (trader expenses, Schedule C): https://www.irs.gov/pub/irs-prior/i1040sd--2021.pdf
- Journal of Accountancy, 2026 inflation adjustments (Rev. Proc. 2025-32): https://www.journalofaccountancy.com/news/2025/oct/annual-inflation-adjustments-announced-for-tax-year-2026/
- Accounting Today, 2026 brackets: https://www.accountingtoday.com/news/irs-announces-inflation-adjustments-for-2026
- CPA Practice Advisor, 2026 brackets: https://www.cpapracticeadvisor.com/2025/10/09/irs-adjusts-tax-brackets-standard-deduction-for-2026/170661/
- KPMG, broker wash-sale reporting scope: https://kpmg.com/kpmg-us/content/dam/kpmg/taxnewsflash/pdf/2022/07/22208.pdf
- Marcum, 1099-B wash sales and cross-account gaps: https://marcumllp.com/insights/dont-be-surprised-by-the-new-look-of-your-1099b
- TaxAct, Form 8949 Exception 1/2 summary reporting: https://support.taxact.com/support/960/form-1099-b-separate-line-reporting-exceptions-schedule-d-or-8949-summary-totals
- Thomson Reuters UltraTax, Form 8949 substitute statement / Form 8453: https://www.thomsonreuters.com/en-us/help/ultratax-cs/1040/capital-gains/form-8949-substitute-paper-copy
- Green Trader Tax (via MoneyShow) on year-end wash-sale deferral: https://moneyshow.com/articles/tradingidea-59563
- DayTradingZ wash-sale rule for day traders: https://daytradingz.com/wash-sale-rule-day-trading/
- Weaver, NIIT overview: https://weaver.com/resources/understanding-the-net-investment-income-tax-niit-what-investors-need-to-know/
- Seward & Kissel, NIIT and trader funds / §475: https://sewkis.com/?p=2174
- Schwab, Tax strategies for traders (TTS, NIIT, MTM): https://www.schwab.com/learn/story/mark-to-market-trader-taxes
- Estimated-tax safe harbors (secondary): https://fraimcpa.com/safe-harbor-rule-how-to-avoid-irs-penalties/ ; https://beancount.io/blog/2026/08/13/110-percent-safe-harbor-estimated-tax-high-earners-guide
- NJ capital losses (NJBiz): https://njbiz.com/how-to-handle-your-capital-gains-or-losses-how-you-act-can-make-all-the-difference-come-tax-time
- NJ capital gains (Edelman): https://www.edelmanfinancialengines.com/education/tax/capital-gains-tax-new-jersey/
- California R&TC §17570 (conformity to §475 election): https://law.justia.com/codes/california/code-rtc/division-2/part-10/chapter-6/section-17570
- OBBBA individual provisions (Bond Schoeneck & King): https://www.bsk.com/news-events-videos/top-10-tax-takeaways-from-the-one-big-beautiful-bill-act

---

## 2. Trader tax status (TTS) and the §475(f) mark-to-market election

### Short answer
TTS is a facts-and-circumstances position, not an election or an IRS approval: the activity must be substantial, continuous and regular, and aimed at profiting from short-term daily price swings. Case law and practitioners point to roughly 500–1,000+ trades a year, trading on ~75% of market days, average holding periods well under 31 days, and several hours a day. TTS lets the trader deduct business expenses on Schedule C; gains stay capital (no SE tax) unless §475(f) is elected. §475(f) converts trading gains/losses to ordinary, removes the wash-sale rule and the $3,000 loss cap, and requires a year-end mark to market; an existing individual must elect by the unextended due date of the prior year's return (April 15 of the election year), a new entity can elect within 2 months and 15 days of formation, and the election binds until revoked under the automatic-consent procedure with the same prior-year deadline. A bounded-window, part-time system trading hundreds of times a month on most market days has a plausible but not assured TTS claim; the part-time element is the main weakness.

### Detail

**IRS criteria (Topic 429 / Pub. 550).** All three must be met: (1) you seek to profit from daily market movements in prices, not from dividends, interest or capital appreciation; (2) your activity is substantial; (3) you carry it on with continuity and regularity. Facts considered: typical holding periods, frequency and dollar amount of trades during the year, the extent to which the activity produces income for a livelihood, and the time devoted. No IRS application or approval exists; the position is taken on the return.

**Tax Court benchmarks (as summarized by practitioners; opinions not read directly).**
- *Holsinger* (T.C. Memo 2008-191): 372 options trades on ~45% of trading days — denied; Green calls it a close call.
- *Endicott* (T.C. Memo 2013-199): 204 trades/75 days (2006), 303 trades/99 days (2007), ~1,543 trades (2008) but 35-day average holding period and substantial dividend income — denied. The IRS argued the average holding period must be 31 days or less; the court treated holding period as the most important factor.
- *Nelson* (T.C. Memo 2013-259): 535 trades on 121 days (48% of trading days) in 2005; 235 trades on 66 days (26%) in 2006 — denied; court said a trader transacts "on an almost daily basis."
- *Chen* (T.C. Memo 2004-132): trades concentrated in three months — denied as sporadic.
- *Assaderaghi* (T.C. Memo 2014-33): taxpayer with a full-time engineering job — denied (details UNCONFIRMED).
- *Poppe* (T.C. Memo 2015-205): ~60 trades/month (≈720/yr), 4–5 hours/day, traded mostly in the last hour of the day — TTS granted (though he lost on the §475 election for failing to follow Rev. Proc. 99-17).
- Practitioner rules of thumb: Green Trader Tax's "golden rules" — 500+ round-trip trades/year (≈1,000 executions), trading on ~75% of available days (≈4 days/week), average holding period under 31 days, 4+ hours/day including research, no multi-month lapses, meaningful account size, intention to run it as a business. Other sources cite 720 or 1,000+ trades. None is statutory.

**What TTS changes.** Trading expenses (data, software, hardware, home office, education after start, margin interest) become Schedule C business deductions instead of non-deductible investment expenses (miscellaneous itemized deductions are suspended/permanently repealed). Gains and losses remain capital unless §475 is elected; Schedule C typically shows expenses only and a loss. Trading gains are excluded from self-employment income (IRC §1402(a)(3)(A)) whether or not §475 is elected (§475(f)(1)(D)), so no SE tax — which also means no earned income for retirement-plan or health-insurance deductions (see §4). TTS trading is a specified service trade or business for §199A, so the QBI deduction phases out at higher incomes.

**§475(f) mark-to-market election.**
- Effect: securities held in the trading business are treated as sold at fair market value on the last business day of the year; all gains and losses are ordinary (reported on Form 4797 Part II with an attached statement); the wash-sale rule does not apply to securities held in connection with the trading business (Form 4797 instructions); no $3,000 capital-loss cap; net losses become part of an NOL (carryforward only since 2018, limited to 80% of taxable income, except for the suspended carryback years). Ordinary income is not SE income. Investment positions can be held outside the election only if contemporaneously identified in the books and records; practitioners recommend a separate account or entity to segregate them. Downsides: loss of long-term capital-gain rates on any held positions (irrelevant to a pure intraday system), unrealized year-end gains are taxed, and the §475 ordinary income is still NII.
- Deadline for an existing individual taxpayer (Rev. Proc. 99-17 §5.03(1)): file the election statement by the due date **without extensions** of the prior year's return — i.e., by April 15, 2026 for tax year 2026 — attached either to that return or to the Form 4868 extension request. Then file Form 3115 with the election-year return. The IRS has repeatedly denied §9100 relief for late elections (PLRs 202145015, 202325003 among others) and the Tax Court in *Poppe* held that failing to follow Rev. Proc. 99-17 means no valid election. **For this user, the earliest effective year for an individual election is now 2027 (statement due April 15, 2027).**
- New taxpayer route (Rev. Proc. 99-17 §5.03(2)): a taxpayer not required to file a return for the preceding year (a newly formed entity) elects by placing the statement in its books and records within 2 months and 15 days after the first day of its first tax year, then attaches a copy to its first return. This is how practitioners obtain a mid-year §475 election via a new LLC/partnership or S corp.
- Revocation: since Rev. Proc. 2015-14 (carried into the annual automatic-change procedures) revocation is automatic-consent but must be requested by the same prior-year unextended due date, so it takes effect only prospectively and cannot be done with hindsight. The election is therefore "sticky" by at least one full year and cannot be toggled year-to-year to cherry-pick capital vs. ordinary treatment. If TTS is lost in a later year, the election goes dormant for that year.

**Would this system plausibly qualify?** Points for: hundreds of trades a month easily clears any volume benchmark; intraday holding periods are the strongest possible fact on the holding-period factor; a systematic, journaled process with regular daily execution demonstrates continuity and business-like conduct. Points against: the IRS and courts are skeptical of part-time traders, especially those with full-time employment; a "bounded window" (e.g. trading only part of the session) is not fatal — *Poppe* traded mostly the last hour and won — but hours devoted and dependence on the income for a livelihood are weighed. The number of **days** traded matters more than the number of trades: the system should run on ~75% of trading days or more, with no multi-week lapses. Also, a ~$1–$5 stock universe with small account size could cut against "substantial" in dollar terms. Verdict: plausible, not assured; a CPA experienced with TTS should assess the actual pattern after a few months of live logs.

### Design implications for this system
- The journal should natively produce the TTS evidence file: number of executions and round trips per month, number of distinct trading days vs. available market days (percentage), average and median holding period, hours of system/operator activity per day, dollar volume, and a continuity chart showing no gaps. This is exactly what the Tax Court looks at.
- Keep a dated "trading business plan" and expense log from day one (Schedule C support).
- Calendar the §475(f) decision: statement due April 15 of the election year for an individual; if the user forms an entity, the 75-day clock starts at formation. Build the P&L reporting so that it can switch between Schedule D/8949 (capital) and Form 4797 (ordinary) presentation.
- If §475 is elected, the wash-sale engine and the year-end flatten rule become unnecessary for the trading account, but any investment holdings must be segregated (separate account) and identified.
- Never hold investment positions in the trading account.

Confidence: **high** on IRS criteria, §475 mechanics and deadlines (primary sources: Topic 429, Rev. Proc. 99-17, Form 4797 instructions); **medium** on case-law numeric details (practitioner summaries); **low-medium** on the qualification verdict for a part-time system (inherently judgmental).
Consult a professional? **Yes, strongly** — TTS and §475 are the two decisions a trader-specialist CPA should make with the user before the first full tax year.

### Sources
- IRS Topic 429: https://www.irs.gov/taxtopics/tc429
- Rev. Proc. 99-17 (IRS PDF): https://www.irs.gov/pub/irs-drop/rp-99-17.pdf
- IRS Instructions for Form 4797 (2025), §475 traders: https://www.irs.gov/instructions/i4797
- IRS PLR on late §475 election denied (example): https://www.irs.gov/pub/irs-wd/0927005.pdf
- Tax Notes, IRS denies late MTM election: https://www.taxnotes.com/research/federal/irs-private-rulings/letter-rulings-technical-advice/irs-denies-extension-to-make-mark-to-market-election/1kfkw
- EY, Tax Court finds taxpayer failed to properly make MTM election (Poppe): https://taxnews.ey.com/news/2016-1939-tax-court-finds-that-taxpayer-failed-to-properly-make-a-mark-to-market-election
- Poppe T.C. Memo 2015-205 (PDF): https://bradfordtaxinstitute.com/Endnotes/TC_Memo_2015-205.pdf
- Journal of Accountancy, The lure of a Sec. 475 election: https://www.journalofaccountancy.com/issues/2014/jul/sec-475-election-20149537/
- Kaufman Rossin, automatic revocation of §475(f) (Rev. Proc. 2015-14): https://kaufmanrossin.com/blog/irs-makes-it-easier-for-hedge-fund-traders-to-revoke-section-475f-election/
- Green Trader Tax, Trader Tax Status: https://greentradertax.com/trader-tax-center/trader-tax-status/
- Green Trader Tax, Holsinger case: https://greentradertax.com/holsinger-case-irs-denies-trader-tax-status-and-mtm/
- Forbes (Green), Tax Court denies investor trader tax breaks (Endicott): https://www.forbes.com/sites/greatspeculations/2013/08/31/tax-court-denies-investor-trader-tax-breaks/
- Withum, Trader vs. investor funds (Endicott, Nelson, Assaderaghi): https://www.withum.com/resources/trader-vs-investor-funds/
- Options Tax Guy, trader tax court cases: https://www.optionstaxguy.com/court-cases
- Porte Brown, SE tax exclusion for trading gains: https://www.portebrown.com/newsblog-archive/how-to-qualify-for-tax-favored-securities-trader-status
- Luckbox, part-time/side-hustle TTS: https://luckboxmagazine.com/?p=8834
- Curved Trading, risks/downsides of §475: https://curvedtrading.com/articles/en/trading/mark-to-market-risks/
- Benzinga (Green), IRS warns Section 475 traders (segregation): https://www.benzinga.com/trading-ideas/14/08/4778335/irs-warns-section-475-traders

---

## 3. Recordkeeping

### Short answer
The IRS expects records sufficient to establish the date acquired, date sold, proceeds, cost basis and adjustments of every security, plus support for any business expenses and for the TTS facts. Retention: at least 3 years after the return is filed (6 years if income is understated by more than 25%, 7 years for worthless-security claims, indefinitely if no return/fraud), and basis records until the limitations period runs for the year the position is disposed of. An append-only trade journal plus broker confirmations/statements/1099-Bs comfortably satisfies this. An individual customer has **no** FINRA or SEC books-and-records obligation; Rules 17a-3/17a-4 and FINRA 4511 bind broker-dealers only.

### Detail
- IRS "How long should I keep records": 3 years generally; 6 years if you omit more than 25% of gross income (and, per the same framework, if basis is substantially overstated); 7 years for worthless securities or bad-debt deductions; 4 years for employment tax records (relevant if an S corp pays salary); indefinitely for no return or fraudulent return. Property/basis records must be kept until the period of limitations expires for the year of disposition. Electronic records are acceptable (Rev. Proc. 97-22) if they are accurate, accessible and reproducible.
- Pub. 550 / Pub. 552 expectations for securities: confirmations, brokerage statements, 1099-Bs, records of reinvested dividends, splits and corporate actions affecting basis, records supporting wash-sale adjustments. FINRA investor guidance echoes that brokers are not required to keep transaction records indefinitely and investors should keep their own.
- For TTS/Schedule C: expense receipts, time logs, the business plan, and the trading-activity statistics above. For §475: the election statement, Form 3115, and contemporaneous identification of any investment positions.
- Journal + broker statements: the journal gives the timestamped order/fill detail and the taxpayer's own lot/wash computation; broker statements and the 1099-B are the third-party corroboration. Together these exceed what the IRS requires. An append-only design (hash-chained or write-once) is not required by any rule but strengthens credibility of contemporaneous records, which matters most for TTS and §475 identification disputes.
- FINRA/SEC: Exchange Act Rules 17a-3 and 17a-4 and FINRA Rule 4511 impose creation and retention duties on broker-dealers (including customer account records). Nothing in those rules reaches a natural-person customer trading their own account. Penny-stock Rules 15g-2/15g-9 and FINRA day-trading Rules 2130/2270 similarly impose duties on the firm, with the customer only signing acknowledgments. Confirmed by absence: no source suggests any individual-customer recordkeeping rule, and the rule texts are addressed to "every broker or dealer."

### Design implications for this system
- Retain the journal, broker confirmations, monthly statements, 1099-Bs and tax returns for at least 7 years; practically, keep them forever (storage is cheap). Export annual snapshots in a durable format (CSV + PDF) separate from the live database.
- Store corporate-action events (splits, symbol changes, delistings) because they affect basis and "substantially identical" determinations.
- Keep the expense log and time log inside the same system so TTS evidence is contemporaneous.
- No regulatory reporting or retention format is imposed on the individual; design for IRS audit reproducibility, not for SEC 17a-4 WORM compliance.

Confidence: **high**.
Consult a professional? **No** for retention design; **yes** only if an entity with payroll is created (employment-tax records).

### Sources
- IRS, How long should I keep records?: https://www.irs.gov/businesses/small-businesses-self-employed/how-long-should-i-keep-records
- FINRA, The importance of investment recordkeeping: https://www.finra.org/investors/insights/recordkeeping
- SEC Release 34-47570, Books and records requirements for brokers and dealers: https://www.sec.gov/rule-release/34-47570
- Temple Law 10-Q, Broker-dealer recordkeeping requirements (17a-3/17a-4, FINRA 4511): https://law.temple.edu/10q/broker-dealer-recordkeeping-requirements/
- Global Relay, SEC Rules 17a-4 and 17a-3 explained: https://www.globalrelay.com/resources/the-compliance-hub/rules-and-regulations/sec-rules-17a-4-and-17a-3-explained/
- Rev. Proc. 97-22 electronic records (secondary summary): https://beancount.io/blog/2026/05/22/how-long-to-keep-business-records-irs-statute-of-limitations-3-6-7-years-employment-tax-4-years-rev-proc-97-22-electronic-recordkeeping-document-retention-schedule-guide

---

## 4. Entity structures for active traders (CPA question)

### Short answer
Practitioners (chiefly Green Trader Tax and similar TTS specialists) recommend: (a) stay a sole proprietor if the only goal is TTS/Schedule C and possibly §475; (b) form a single-member LLC taxed as an S corp (or a spousal partnership/LLC) when the trader wants to deduct health-insurance premiums and make Solo 401(k) contributions, which require earned income that trading gains cannot provide; (c) use a new entity to obtain a mid-year §475 election via the 75-day new-taxpayer rule. Costs: payroll administration, separate returns, state franchise/minimum taxes (California $800/yr minimum plus LLC gross-receipts fee; many states charge $0–$300; some charge more), and — a real operational cost for a software system — market-data vendors and brokers classify entity accounts as **professional** subscribers, raising exchange data fees from a few dollars to tens or hundreds of dollars per feed per month. **This whole section is a CPA question.**

### Detail
- Sole proprietor with TTS: Schedule C for expenses, Schedule D/8949 or Form 4797 for trading. Cannot pay itself wages, so no health-insurance deduction (above-the-line) and no retirement-plan contributions from trading profits. Simplest, no franchise tax, individual election deadlines apply.
- Single-member LLC (disregarded): liability ring-fencing (of limited value for a long-only cash account with no outside creditors), potential state SALT-cap workaround via PTE taxes in some states, and a vehicle for the new-taxpayer §475 election if formed mid-year. Alone it changes nothing about earned income. Entity accounts are harder to open and have professional data status.
- S corporation (LLC electing S status): the trader pays themselves a reasonable salary from trading profits late in the year (often via a payroll service, ~$600+/yr); the salary is earned income supporting a Solo 401(k) (employee deferral + employer profit-sharing contribution) and health-insurance premiums reimbursed through payroll (deductible, not subject to FICA on the premium portion but the salary itself incurs FICA and Medicare, which trading gains otherwise avoid). Deductible only for months the S corp operated with TTS. Requires an 1120-S, W-2s, state payroll registrations. Section 199A: TTS is an SSTB, so QBI benefits phase out above the thresholds.
- C corporation: generally not recommended for traders (double tax on distributions, capital losses trapped).
- Partnership (spousal or with a nominal partner): sometimes used for similar reasons; guaranteed payments can be earned income.
- State franchise/minimum taxes: California $800 minimum franchise tax on LLCs and S corps plus an LLC fee starting at $900 for gross receipts over $250k (trading gross proceeds can count — CPA question); Texas franchise tax applies above a high threshold; Delaware $300 LLC tax; New York LLC filing fee; many other states $0–$150. Verify for the user's state.
- Market data: exchanges (NYSE, Nasdaq, OPRA, CME) define "non-professional" as a natural person using data for personal investment. IBKR and most brokers classify corporations, LLCs and partnerships as professional by default; the non-professional questionnaire must be re-affirmed and misrepresentation risks reclassification and back-billing. Professional fees are an order of magnitude higher (e.g. CME $105/month/market pro vs. $1 non-pro top-of-book; Nasdaq/NYSE pro feeds commonly $20–$70+ each per month vs. $1–$5 non-pro — exact figures UNCONFIRMED here, check the broker's data schedule). Some brokers also restrict API access or margin for entity accounts. For a software-driven system, the data classification is also independently sensitive: using data for anything beyond personal investing (e.g. a business entity) is professional use regardless of entity.

### Design implications for this system
- Build the system account-agnostic: the broker account identifier and tax-entity type should be configuration, so a later migration to an LLC/S-corp account does not require code changes. Expect to re-key API credentials and data subscriptions.
- Budget line for professional market-data fees if an entity is used; this may materially change the economics of a small $1–$5 stock strategy.
- Capture gross proceeds totals (not just net P&L) because some state entity taxes/fees key off gross receipts.
- Do not form an entity for tax reasons without a CPA modeling the breakeven (payroll cost + franchise tax + data fees + return prep vs. health-insurance and 401(k) deductions). Typical practitioner guidance is that the S-corp route pays off only with consistent six-figure trading profits.

Confidence: **medium** (practitioner consensus is clear; dollar thresholds and state details vary and were not all confirmed from primary sources).
Consult a professional? **Yes — this entire section is a CPA (and possibly state tax) question.**

### Sources
- Green Trader Tax, Trader Tax Status: https://greentradertax.com/trader-tax-center/trader-tax-status/
- Green Trader Tax, Health insurance and retirement plan contributions: https://greentradertax.com/trader-tax-center/trader-tax-status/employee-benefit-plans/
- Green Trader Tax, Tax planning for S-Corps: https://greentradertax.com/tax-planning-for-s-corps/
- Forbes (Green), How to set up a trading business for optimal tax savings (2022): https://www.forbes.com/sites/greatspeculations/2022/06/20/how-to-set-up-a-trading-business-for-optimal-tax-savings/
- TSCPA, LLC and entity structure for traders: https://tscpatax.com/articles/trader-llc-entity-structure-guide
- Interactive Brokers, Subscribing to data (pro vs non-pro, entities): https://www.interactivebrokers.com/campus/trading-lessons/subscribing-to-data/
- IBKR Knowledge Base, Changing market data subscriber status: https://ibkb.interactivebrokers.com/ja/node/2740
- WatersTechnology, Brokers tackle pro v. non-pro data cost and compliance: https://www.waterstechnology.com/data-management/4623751/brokers-tackle-pro-v-non-pro-data-cost-compliance-challenges
- Rev. Proc. 99-17 §5.03(2) new-taxpayer election: https://www.irs.gov/pub/irs-drop/rp-99-17.pdf

---

## 5. OTC market constraints for the future extension

### Short answer
Since the September 28, 2021 compliance date of amended SEC Rule 15c2-11, broker-dealers may publish quotes in an OTC stock only if current issuer information is publicly available; shells get at most 18 months of piggyback quoting; names without current information drop to OTC Markets' **Expert Market** (quotes visible only to broker-dealers and sophisticated investors, unsolicited customer orders only) or the unquoted **Grey Market**. OTC Markets' tiers today are OTCQX, OTCQB, OTCID (launched July 1, 2025, replacing Pink Current), Pink Limited, and Expert Market, plus the Caveat Emptor flag, which most retail brokers treat as liquidate-only. An SEC trading suspension (up to 10 business days, §12(k)) breaks piggyback eligibility, so quoting generally does not resume when the suspension ends. The penny-stock rules (15g-2 to 15g-9) impose duties on the broker, not the trader: a risk disclosure document with signed acknowledgment before the first trade, and for *recommended* trades a suitability determination and signed purchase agreement (waived for established customers and unsolicited orders). Exchange-listed stocks under $5 are **not** penny stocks (Rule 3a51-1 excludes NMS/exchange-listed securities), so the current $1–$5 listed universe is outside these rules. Brokers with APIs: Interactive Brokers (yes, Fixed schedule), TradeStation (yes, $0.005/share, $1 min, $50 max, 5% notional cap), Schwab ($6.95 per OTC trade online; API OTC support UNCONFIRMED), Tradier (no OTC at all).

### Detail

**Rule 15c2-11 as amended (Release 34-89891, effective Dec 28 2020, compliance Sept 28 2021).** A broker-dealer may initiate or continue a quotation in a non-exchange-listed security only if specified issuer information is current and publicly available (for SEC reporting issuers, filed within 180 days of period end; for non-reporting issuers, OTC Markets' Alternative Reporting Standard disclosure). The "piggyback" exception (relying on another dealer's existing quotes) now requires current public information; it is lost if quotations are interrupted for more than 4 consecutive business days, during and for 60 days after an SEC trading suspension, and for shell companies after 18 months from the initial priced quotation. Result: on Sept 28 2021 more than 2,000 issuers moved from Pink to the Expert Market. The SEC declined in August 2021 to grant a general Expert Market exemptive order (proposed Release 34-90769) and has issued only rounds of limited no-action/exemptive relief since (Commissioner Peirce has criticized the resulting uncertainty). FINRA Rule 6432 requires the Form 211 filing (now generally submitted via OTC Markets as a qualified IDQS). 2026 developments: on March 16, 2026 the SEC proposed to confine 15c2-11 to *equity* securities (a fixed-income carve-out; no change to equity mechanics); a May 2026 rulemaking petition asks for automatic proprietary-quote eligibility for issuers current in their disclosure. Neither restores retail quoting in Expert Market names.

**Expert Market and Grey Market.** Expert Market: an OTC Markets venue where broker-dealers may post quotes representing *unsolicited* customer limit orders in securities lacking current information; quotes are hidden from the public and shown only to broker-dealers and professional/sophisticated investors; OTC Markets does not itself restrict who may trade, but most retail brokers restrict customers to liquidating (sell-only) orders or require order-by-order non-affiliate/unsolicited affirmations. Grey Market: no quotes published by any broker-dealer anywhere; trades occur only by matching unsolicited orders between brokers. In practice a retail account cannot reliably *buy* in either; a long-only system cannot operate there, and a position can become un-sellable at any public price if its name drops to the Expert Market.

**OTC Markets tiers (current).** OTCQX (best market; financial standards, $0.25 minimum bid, sponsor/advisor, no shells or penny-stock-rule-subject issuers), OTCQB (venture market; $0.01 minimum bid, current reporting, annual certification), OTCID (Basic Market, launched July 1, 2025, replaces Pink Current Information; requires baseline disclosure plus management certification and profile verification; ~1,240 securities at launch), Pink Limited (limited or outdated information, a warning tier), Expert Market (no current information / restricted). Caveat Emptor is a flag, not a tier: applied for promotion/spam campaigns, suspected fraud or investigation of insiders, regulatory suspensions, unexplained corporate actions or extreme unexplained price moves; while flagged, quotes for any stock not in a current-information tier are blocked on otcmarkets.com; Fidelity (2016), E*Trade (2020), TD Ameritrade/Schwab (2021), Robinhood and Webull all block opening purchases in CE names. OTC Markets also publishes "Shell Risk," "Promotion," "Delinquent SEC reporting" and "Bankruptcy" flags in its Compliance Data File, available as a licensed data feed.

**SEC trading suspensions.** Under Exchange Act §12(k) the SEC may suspend trading for up to 10 business days, typically for lack of current information, questions about accuracy of public statements, or manipulation/promotion. Consequence under amended 15c2-11: the suspension breaks the piggyback exception, so after expiry no broker-dealer may quote until it conducts a full information review and files Form 211 (FINRA 6432); many suspended names go straight to the Grey/Expert Market with CE flags. The SEC's suspensions page (sec.gov → Litigation → Trading Suspensions) lists orders; 2025–2026 activity included batches of delinquent filers (14 issuers April 2025) and, in April 2026, 14 recent Asia-based Nasdaq/NYSE IPOs suspended for suspected manipulation — a reminder that suspensions also hit *listed* small caps in the $1–$5 range, not just OTC names.

**Penny stock rules (Exchange Act §3(a)(51), Rule 3a51-1, Rules 15g-1 to 15g-9).** A penny stock is an equity security not listed on a national exchange (NMS), priced under $5, and not meeting net-tangible-asset/revenue tests. Exchange-listed stocks, even under $5, are excluded — so the current strategy universe is not subject to these rules. For non-exempt penny-stock transactions the broker-dealer must: (15g-2) deliver the standardized Schedule 15G risk disclosure document and obtain a signed and dated acknowledgment before the customer's first penny-stock transaction, and wait two business days after sending it; (15g-3) disclose current quotations; (15g-4) disclose its compensation; (15g-5) disclose the associated person's compensation; (15g-6) send monthly account statements with market values; (15g-9) for *recommended* (solicited) transactions to non-established customers, obtain financial information, make and deliver a written suitability determination, and receive the customer's signed written agreement to the specific purchase before executing. 15g-1 exemptions: unsolicited transactions (no recommendation) are exempt from 15g-9 but not from the disclosure document; "established customer" (account open with a transaction more than one year ago, or three prior penny-stock purchases on different days in different issuers) waives the suitability/agreement step. A self-directed API-driven account places only unsolicited orders, so the practical requirement is: sign the broker's penny-stock risk disclosure (and the broker's own OTC/low-priced-securities agreement) once, before the first trade, and expect limit-order-only, no GTC in some names, and per-order affirmations in restricted tiers.

**Brokers with APIs that allow OTC for retail.**
- *Interactive Brokers* (confirmed): OTC/pink-sheet stocks are tradable through TWS API / Client Portal API / FIX. IBKR Lite's commission-free pricing excludes non-exchange-listed stocks; such trades are billed under the Fixed schedule: USD 0.005/share, USD 1.00 minimum, 1% of trade value maximum (plus regulatory fees). Pro Tiered also applies to OTC per older IBKR disclosures (USD 0.0035→0.0005/share by volume, $0.35 min, 1% max, plus exchange/clearing pass-throughs). IBKR restricts or blocks some Expert Market/Grey/CE names (a UK ombudsman case shows a block on Grey Market purchases). Exact OTC-specific exceptions UNCONFIRMED; check the IBKR OTC commission page.
- *TradeStation* (confirmed): offers OTC equities via its WebAPI; official pricing disclosure: $0.005/share for all OTC executions, $1.00 minimum, $50.00 maximum per order, capped at 5% of notional; OTC trades excluded from volume tiers. Review sites claiming "commission-free OTC" conflict with the official page.
- *Schwab / thinkorswim* (partial): U.S. OTC equities $6.95 per online trade ($6.95 + $25 broker-assisted; $5 automated phone). Schwab does not support all pink-sheet securities and liquidates-only on CE names. The Schwab Trader API (individual) supports US equities/ETFs/options; whether OTC symbols are orderable through the API is **UNCONFIRMED** — check developer.schwab.com or test in paper.
- *Tradier* (confirmed negative): "Pink Sheets / OTCBB securities (over-the-counter securities not listed on the National Market System) are also excluded"; Tradier supports only exchange-listed US stocks. Not usable for the OTC extension.

### Design implications for this system
- Treat OTC as a separate venue class in code: require a per-symbol tier/flag check (OTCQX/OTCQB/OTCID only; reject Pink Limited, Expert Market, Grey, Caveat Emptor, Shell Risk, Promotion-flagged) before any entry; license or scrape OTC Markets' compliance/tier data daily.
- Add a hard rule: liquidate or block entry when a name is downgraded, suspended, or CE-flagged, and model the risk that a held position becomes un-sellable to retail (Expert Market), i.e., assume non-zero probability of 100% loss of liquidity.
- Expect limit orders only, no market orders, possibly no GTC, wider spreads and manual broker affirmations; the API path should fail gracefully on broker-side rejects for restricted symbols.
- Commission model must switch from $0 (listed) to per-share/per-order schedules (IBKR Fixed or TradeStation) — this changes the viability of small-dollar trades; the $1 minimum alone is 1% of a $100 fill.
- Complete the broker's penny-stock/OTC risk-disclosure acknowledgment before the first OTC order; the system cannot trade OTC until that is on file.
- Listed stocks $1–$5 are not penny stocks and are not touched by 15c2-11, but *are* exposed to SEC suspensions and exchange delisting to OTC (price below $1 for 30 days → compliance notice → delisting). Monitor exchange compliance notices for held names so a listed position does not become an OTC position by surprise.

Confidence: **high** on 15c2-11 mechanics, tiers, CE and penny-stock rules (primary/official sources); **medium** on broker commission schedules (official pages surfaced for TradeStation and Schwab; IBKR OTC-specific wording partly from older disclosures); **low** on Schwab API OTC support and the exact current Expert Market retail buy policy per broker.
Consult a professional? **Partly** — a securities lawyer is not needed for a self-directed retail account; confirm broker-specific OTC policies with each broker's support before building.

### Sources
- SEC, proposed conditional exemptive order for Expert Market (Release 34-90769): https://www.sec.gov/file/34-90769
- Federal Register, Rule 15c2-11 amendments (85 FR 68124): https://www.govinfo.gov/link/fr/85/68203
- SEC press release 2026-28, proposed 15c2-11 amendments (equity-only): https://www.sec.gov/newsroom/press-releases/2026-28-sec-proposes-amendments-exchange-act-rule-15c2-11
- Federal Register, March 19 2026 proposal: https://www.federalregister.gov/documents/2026/03/19/2026-05401/publication-or-submission-of-quotations-without-specified-information
- SEC rulemaking petition (May 2026) on automatic quote eligibility: https://www.sec.gov/rules-regulations/2026/05/petition-rulemaking-amend-rule-15c2-11-establish-automatic-proprietary-quote-eligibility-otc-issuers
- Sidley, SEC proposes to limit 15c2-11 to equity securities: https://www.sidley.com/en/insights/newsupdates/2026/03/us-sec-proposes-to-limit-rule-15c2-11-to-equity-securities
- Hinckley Allen, 15c2-11 key changes (piggyback, shells, suspensions): https://www.hinckleyallen.com/publications/sec-revises-exchange-act-rule-15c2-11-key-changes-to-retail-investor-protections-and-quotations-for-over-the-counter-securities/
- Securities Lawyer 101, amended 15c2-11 and shell companies (18 months): https://www.securitieslawyer101.com/2021/the-amended-rule-15c2-11-is-bad-news-for-shell-vendors
- Olshan, 2,000+ companies shifted to Expert Market: https://olshan2.sitepilot09.firmseek.com/Securities-Law-Blog/more-than-2-000-publicly-traded-companies
- Securities Law Blog (Anthony), SEC denies Expert Market for now: https://securities-law-blog.com/2021/08/17/sec-denies-expert-market-for-now/
- OTC Markets blog, Understanding the Expert Market: https://blog.otcmarkets.com/2021/03/25/understanding-the-expert-market/
- OTC Markets blog, The Expert Market's larger role post 15c2-11: https://blog.otcmarkets.com/2023/09/14/the-expert-market-its-larger-role-post-rule-15c2-11/
- OTC Markets blog, 3 things to know about the launch of OTCID: https://blog.otcmarkets.com/2025/04/23/3-things-you-need-to-know-about-the-launch-of-otcid/
- OTC Markets press release, OTCID launch (July 1 2025): https://www.nasdaq.com/press-release/otc-markets-group-launches-otcidtm-basic-market-major-structural-upgrade-us-otc
- OTC Markets Compliance Data File spec (CE, Shell Risk flags): https://www.otcmarkets.com/files/OTC%20Markets%20Compliance%20Data%20File%20Specification%20-%20v2.4.pdf
- Securities Lawyer 101, OTC tiers 2026: https://www.securitieslawyer101.com/2026/08/07/otc-markets-listing-requirements/
- Benzinga, OTC Markets warning symbols (Caveat Emptor): https://benzinga.com/article/13040272
- Securities Lawyer 101, TD Ameritrade restricts CE orders to liquidating: https://www.securitieslawyer101.com/?p=82827
- Webull OTC trading disclosure: https://www.webull.com/zh/policy/VOGGHGJ3BONAC8CTK63TRA3GD9_2.0
- SEC opinion, Nano Magic (suspension and loss of piggyback eligibility): https://www.sec.gov/files/litigation/opinions/2024/34-99980.pdf
- Securities Lawyer 101, SEC trading suspensions 101: https://www.securitieslawyer101.com/sec-trading-suspensions-101/
- Cooley, April 2026 suspensions of 14 Asia-based IPO issuers: https://sle.cooley.com/2026/04/
- Courthouse News, SEC stops trading in 14 firms' shares (April 2025): https://api.courthousenews.com/sec-stops-trading-in-14-firms-shares/
- FINRA Notice 93-55 (Rule 15g-2 acknowledgment): https://finra.org/rules-guidance/notices/93-55
- FINRA Notice 92-38 (penny stock rules): https://finra.org/rules-guidance/notices/92-38
- Federal Register PRA notice, Rule 15g-9 retention: https://www.govinfo.gov/content/pkg/FR-2014-09-12/pdf/2014-21736.pdf
- Lawcast, penny stock rules and broker-dealers: https://lawcast.com/2014/11/04/penny-stock-rules/
- Rule 3a51-1 definition (as quoted in SEC filings): https://www.sec.gov/Archives/edgar/data/0001013453/000101345301000010/0001.txt
- Interactive Brokers, Commissions (US stocks Fixed/Tiered): https://www.interactivebrokers.com/commissions
- IBKR disclosure, Lite excludes non-exchange-listed stocks (Fixed pricing applies): https://interactivebrokers.com/en/index.php?f=45443
- TradeStation, Stocks & ETFs pricing disclosures (OTC $0.005/share, $1 min, $50 max): https://www.tradestation.com/stocks-etfs-pricing-disclosures/
- Schwab pricing (OTC $6.95): https://www.schwab.com/pricing
- Brokerage-Review, Schwab penny/OTC rules 2026: https://www.brokerage-review.com/discount-broker/pennystocks/charlesschwab-pennystocks.aspx
- Tradier support, FAQ (no OTC/pink sheets): https://support.tradier.com/kb/guide/en/frequently-asked-questions-IZvpnTjVwe/Steps/4702203,4702252,4532345,4532929
- Tradier pricing page (no opening OTC orders): https://tradier.com/individuals/pricing
- StockBrokers.com, best brokers for penny stock (OTC) trading: https://www.stockbrokers.com/guides/pennystocks
- MyLinedChart, Schwab API scope: https://mylinedchart.com/resources/articles/schwab-api-for-technical-traders-workflow-fit-checklist

---

## 6. 2025–2026 legislative and regulatory changes affecting retail short-term traders

### Short answer
Enacted: (1) OBBBA (July 4, 2025) made the TCJA individual rate brackets permanent — no capital-gains rate changes, no wash-sale changes for securities; (2) FINRA's elimination of the Pattern Day Trader rule (SEC approved SR-FINRA-2025-017 on April 14, 2026; Regulatory Notice 26-10; effective June 4, 2026, broker phase-in permitted until October 20, 2027), replacing the $25,000 minimum and day-trade count with an intraday margin standard — the most consequential operational change for this system; (3) SEC Reg NMS amendments (Release 34-101070): half-penny ticks for tick-constrained stocks and lower access-fee caps with a November 2025 compliance date, round-lot redefinition by price, and odd-lot data in the SIP by May 2026. Proposed/pending: wash-sale extension to digital assets (Lummis PARITY Act S. 2025; Miller–Horsford bill; House Ways & Means action September 2026) — does not touch stocks; Wall Street Tax Act of 2025 (S. 2127) FTT phasing 0.02%→0.1% — referred to Finance, no movement; SEC March 2026 proposal to narrow 15c2-11 to equities; SEC's September 30, 2026 "retailization of private markets" package (irrelevant to equity day trading). No proposal found to change short-term capital gains treatment, index gains, or restrict retail intraday trading.

### Detail
- **OBBBA (P.L. 119-21, July 2025).** Permanent 10–37% brackets; higher standard deduction ($16,100/$32,200 for 2026); SALT cap raised to $40,000 with phase-down for high incomes (relevant to state-tax deductibility of trading-state taxes); no change to §1091, §475, NIIT, or capital-gains rates. Capital-gains indexing remains an advocacy idea only; no bill advanced.
- **PDT rule elimination.** FINRA Rule 4210(f)(8)(B) pattern-day-trader provisions (4 day trades in 5 days, $25k minimum equity, day-trading buying power) are replaced by a new intraday margin standard in Rule 4210(d)(2) under which the firm must ensure maintenance-margin-based equity proportional to actual intraday exposure; maintenance margin (25%) unchanged; FINRA Rules 2130 (approval of day-trading accounts) and 2270 (day-trading risk disclosure) still apply. Brokers implemented on different dates (E*TRADE June 9, 2026); firms may phase in until Oct 20, 2027, so individual brokers may still show PDT logic. Effect: the system is no longer forced to a $25k margin account to make more than three day trades a week; a cash account still has free-riding/settled-funds constraints (T+1 settlement since May 2024), so a margin account remains the practical choice for intraday turnover.
- **Reg NMS tick/access-fee/round-lot amendments (adopted Sept 18, 2024).** Minimum quoting increment of $0.005 for NMS stocks whose time-weighted average quoted spread is ≤ $0.015 (evaluated over 3 months, set semiannually); access-fee cap reduced to $0.001 for stocks ≥ $1 (and 0.1% of price for stocks under $1); round lot redefined by price (100 shares for stocks ≤ $250, down to 1 share above $10,000 — so 100 shares for the entire $1–$5 universe); odd-lot information disseminated in consolidated data. Compliance November 2025 for ticks/fees/round lots; May 2026 for odd-lot data. **UNCONFIRMED** whether implementation occurred exactly on schedule or was stayed; the SEC fact sheet and 2024 commentary are the sources found. Stocks in $1–$5 are often tick-constrained at $0.01 and are candidates for $0.005 quoting, which affects spread capture, queue priority and order-pricing logic.
- **Digital-asset wash-sale bills.** Lummis Digital Asset PARITY Act (S., June 2025) and Miller–Horsford discussion draft (Dec 2025) → House bill (reported as H.R. 9172, June 2026; Ways & Means markup Sept 16, 2026 per one source — sources conflict). Would apply §1091 to digital assets only; stocks already covered. Monitor only if crypto-related equities/ETFs enter the universe (they are already securities and already covered).
- **Financial transaction tax.** Wall Street Tax Act of 2025 (S. 2127, Schatz/Van Hollen et al.): 0.02% in 2026 rising to 0.1% after 2029 on stock, bond and derivative trades; referred to Senate Finance; no committee action; House companion H.R. 4035 status unclear. At 0.1% round trip = 0.2% of notional — would be material for a high-turnover $1–$5 strategy if ever enacted; negligible probability in the 119th Congress.
- **SEC (Chair Atkins) agenda.** July 7, 2026 regulatory-agenda statement emphasizes revitalizing public markets; September 30, 2026 proposals expand retail access to private markets (interval funds, performance fees, accreditation by exam) — not relevant to listed equity trading. March 2026 15c2-11 equity-only proposal (see §5). Nothing found restricting retail intraday trading, payment for order flow, or gamification rules (the 2023 "predictive data analytics" proposal was withdrawn in 2025 — **UNCONFIRMED** in this search, from general knowledge). Rule 605 execution-quality disclosures were expanded (2024 adoption, compliance 2025–2026), which gives retail traders better broker execution statistics.
- **No change** found to §475, TTS criteria, estimated-tax rules, or Form 8949/1099-B reporting for equities for 2025–2026. (1099-DA for digital assets began for 2025 transactions — irrelevant to stocks.)

### Design implications for this system
- Do not hardcode the PDT constraint (3 day trades per 5 days under $25k); instead read broker-specific intraday buying-power limits via API, and keep a feature flag for brokers still phasing in through 2027.
- Price/tick logic: support $0.005 increments for tick-constrained NMS stocks; read the SEC/exchange tick-size list semiannually; round-lot = 100 shares for this universe, so odd-lot orders (< 100 shares) still do not set the NBBO.
- Add a cost-model parameter for a hypothetical FTT so strategy viability can be re-tested if S. 2127 ever moves.
- No tax-law change pending that alters the wash-sale/TTS/§475 design in §1–§2; re-check annually each January (Rev. Proc. inflation adjustments, Form 8949 instructions, any §1091 amendment).

Confidence: **high** on PDT elimination and OBBBA (multiple consistent sources incl. FINRA and law firms); **medium** on Reg NMS implementation timing and bill statuses; **low** on anything I marked UNCONFIRMED.
Consult a professional? **No** for monitoring; the CPA engaged under §1–§2 will track tax-law changes.

### Sources
- FINRA weekly update, new intraday margin standards replace day-trading margin requirements (Apr 15 2026): https://www.finra.org/compliance-tools/weekly-archive/04152026
- WilmerHale, SEC approves amendments to FINRA Rule 4210 (Apr 23 2026): https://www.wilmerhale.com/en/insights/client-alerts/20260423-sec-approves-amendments-to-finra-rule-4210-replacing-day-trading-margin-requirements-with-a-modernized-intraday-margin-standard
- King & Spalding, FINRA adopts sweeping changes to day-trading margin: https://www.kslaw.com/insights/articles/finra-adopts-sweeping-changes-to-margin-requirements-for-day-trading
- SECLaw, end of PDT rule (Rules 2130/2270 remain): https://seclaw.com/pattern-day-trader-rule-elimination-defense-view/
- E*TRADE, PDT rule change: https://us.etrade.com/knowledge/library/margin/pattern-day-trading-rule-change
- SEC fact sheet, Release 34-101070 (ticks, access fees, round lots, odd lots): https://sec.gov/files/34-101070-fact-sheet.pdf
- KPMG, Reg NMS amendments reg alert: https://kpmg.com/us/en/articles/2024/market-rules-nms-sec-amendments-reg-alert.html
- Katten, SEC revises tick size, access fees and round lot definition: https://katten.com/sec-revises-tick-size-access-fees-and-round-lot-definition-and-takes-steps-to-disseminate-odd-lot-and-other-better-priced-orders
- Bond Schoeneck & King, OBBBA top 10 tax takeaways: https://www.bsk.com/news-events-videos/top-10-tax-takeaways-from-the-one-big-beautiful-bill-act
- Mondaq, tax provisions in OBBBA: https://www.mondaq.com/unitedstates/tax-authorities/1656218/tax-provisions-in-the-one-big-beautiful-bill-act
- Gordon Law, crypto wash sale rule 2026 (PARITY Act, Miller–Horsford): https://gordonlaw.com/learn/crypto-wash-sale-rule-in-2026-is-the-loophole-finally-closed/
- Bizora, wash sale crypto rules 2026 (H.R. 9172): https://www.bizora.ai/post/wash-sale-rule-crypto
- Wall Street Tax Act of 2025, S. 2127 tracker: https://modernaction.io/bills/s2127-119/action
- NAPA, FTT and retirement savings: https://www.napa-net.org/news-info/daily-news/financial-transaction-tax-attacks-retirement-savings
- SEC, Atkins statement on 2026 regulatory agenda (Jul 7 2026): https://www.sec.gov/newsroom/speeches-statements/atkins-statement-2026-regulatory-agenda-070726
- SEC press release 2026-96, retailization of private markets (Sep 30 2026): https://www.sec.gov/newsroom/press-releases/2026-96-sec-proposes-amendments-expand-responsible-retailization-private-markets
- SEC press release 2026-28, 15c2-11 equity-only proposal: https://www.sec.gov/newsroom/press-releases/2026-28-sec-proposes-amendments-exchange-act-rule-15c2-11

---

## Items not confirmed (summary)
- Exact 2026 bracket cutoffs taken from trade press, not the Rev. Proc. text (differences of ~$25 seen between sources).
- Pennsylvania individual capital-loss carryforward treatment (conflicting sources).
- Washington State capital-gains excise applicability to short-term stock gains.
- Exact professional market-data fee amounts for entity accounts at IBKR.
- Whether Schwab's Trader API accepts OTC symbols.
- IBKR's OTC-specific commission exceptions beyond "Fixed schedule applies."
- Whether the Reg NMS tick/round-lot amendments took effect on the November 2025 schedule without stay.
- Current House bill number/status for the digital-asset wash-sale extension (sources conflict).
- Withdrawal of the SEC predictive-data-analytics proposal (general knowledge, not searched).
- Assaderaghi case trade counts.
