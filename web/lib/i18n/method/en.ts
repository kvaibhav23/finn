// The How it works page, in English. Same shape in every language (type MethodText).

export const method = {
  title: "How FINN checks a promise",
  lede: "FINN reads what a company's management said on its earnings calls, picks out the promises that can be checked later, and checks them against what the company actually filed.",
  steps: [
    { h: "1. Find what was promised", p: "FINN reads the transcripts of the last six earnings calls filed on NSE. It keeps only sentences spoken by management, never analysts, and looks for ones that look ahead: guidance, targets, deadlines." },
    { h: "2. Keep only what can be checked", p: "A language model sorts those sentences: could someone later say whether this came true? “Demand will improve” is too vague; “18 to 20% margin this year” is a promise. The model may only copy words and numbers from the sentence. FINN then confirms the quote appears word for word in the transcript and every number in the target appears in the quote. Anything that fails is discarded." },
    { h: "3. Follow it across calls", p: "The same promise repeated in later calls is joined into one line, so you can see when it was repeated, changed, or quietly stopped being mentioned." },
    { h: "4. Find what actually happened", p: "For company-wide figures such as revenue, profit and margins, FINN computes the actual from the results the company filed with NSE (XBRL), and links the filing. Where companies define a margin their own way, FINN uses the definition that matches a figure management itself reported. For things filings don't cover, like volumes or a plant starting, it uses what management said in a later call, quoted and labelled." },
    { h: "5. Decide by rule", p: "The verdict comes from fixed rules, not from the model:" },
  ],
  pricesTitle: "Prices, results and filings",
  pricesIntro: "Each company page also shows the share price, key numbers and recent filings, all from NSE, refreshed every weekday: once in the evening after the closing prices are published, and again overnight.",
  bullets: [
    { b: "Prices", p: "are NSE's official daily closing prices, not live quotes. Prices before a split or bonus are adjusted so the chart has no false drops. Dotted lines on the chart mark earnings calls; tap one to read what was promised on that call." },
    { b: "Key numbers", p: "such as profit, growth, margin and P/E are computed from the results the company filed with NSE (XBRL). Market cap is shares on issue times the last close. Nothing is estimated: a number that can't be computed from filings is left out." },
    { b: "Filings", p: "are the company's own announcements to NSE, each linking the original document. Routine paperwork is left out. Resignations, auditor changes, pledges, credit ratings and regulatory orders are marked “worth a look” by fixed rules, not by a model." },
    { b: "Signals", p: "are plain facts: how many checkable promises management kept, how the price moved against the Nifty 50, whether delivery is above or below usual, and any filings worth a look. They are not a rating." },
    { b: "Big moves", p: "are flagged when a share moves 5% or more in a day, or at least 2% and three times its usual daily move. FINN lists that day's filings next to it, but never guesses at the reason." },
    { b: "Digest", p: "lists every filing from the 20 companies FINN watches for the window you pick, 24 hours by default. Results, people changes, deals and anything a regulator, auditor, lender or rating agency did come first; orders, dividends and calls next; board meetings and press releases are folded away; routine paperwork is only counted. The order comes from fixed rules on NSE's own category and subject line." },
    { b: "Your alerts", p: "use thresholds you set: a day's price move beyond ±X% (5% to start) or volume above N times its 50-day average (2 times to start), plus filings of the types you choose. They are checked against the last 20 sessions and kept on your device." },
    { b: "New appointees", p: "are described from the company's own filing: SEBI requires a brief profile when a director or key manager is appointed. A small language model picks out the name, role, start date and earlier roles, and every one must appear word for word in the filing or it is dropped. FINN does not read LinkedIn or news." },
  ],
  rerun: "When a company files a new earnings-call transcript or new results, FINN checks its promises again overnight, one company a night.",
  keepTitle: "What to keep in mind",
  keep: "FINN is in beta. Sorting sentences is automated and can be wrong, which is why every verdict shows the exact quote, the page, and the source. Segment targets, such as one business line's margin, can't be checked against company-wide filings and stay unverifiable unless management reports them. Nothing here is investment advice.",
};

export type MethodText = typeof method;
