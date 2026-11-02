import type { Metadata } from "next";

import { VerdictMark } from "@/components/VerdictMark";
import { VERDICTS } from "@/lib/types";
import { MEANING } from "@/lib/verdicts";

export const metadata: Metadata = { title: "How it works" };

const RULES = VERDICTS.map((v) => [v, MEANING[v]] as const);

export default function Method() {
  return (
    <article className="prose">
      <h1>How FINN checks a promise</h1>
      <p className="lede">
        FINN reads what a company&apos;s management said on its earnings calls, picks out the promises that can be
        checked later, and checks them against what the company actually filed.
      </p>

      <h2>1. Find what was promised</h2>
      <p>
        FINN reads the transcripts of the last six earnings calls filed on NSE. It keeps only sentences spoken by
        management, never analysts, and looks for ones that look ahead: guidance, targets, deadlines.
      </p>

      <h2>2. Keep only what can be checked</h2>
      <p>
        A language model sorts those sentences: could someone later say whether this came true? &ldquo;Demand will
        improve&rdquo; is too vague; &ldquo;18 to 20% margin this year&rdquo; is a promise. The model may only copy
        words and numbers from the sentence. FINN then confirms the quote appears word for word in the transcript and
        every number in the target appears in the quote. Anything that fails is discarded.
      </p>

      <h2>3. Follow it across calls</h2>
      <p>
        The same promise repeated in later calls is joined into one line, so you can see when it was repeated,
        changed, or quietly stopped being mentioned.
      </p>

      <h2>4. Find what actually happened</h2>
      <p>
        For company-wide figures such as revenue, profit and margins, FINN computes the actual from the results the
        company filed with NSE (XBRL), and links the filing. Where companies define a margin their own way, FINN uses
        the definition that matches a figure management itself reported. For things filings don&apos;t cover, like
        volumes or a plant starting, it uses what management said in a later call, quoted and labelled.
      </p>

      <h2>5. Decide by rule</h2>
      <p>The verdict comes from fixed rules, not from the model:</p>
      <dl>
        {RULES.map(([v, text]) => (
          <div key={v} style={{ display: "contents" }}>
            <dt><VerdictMark verdict={v} /> {v}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>

      <h2>Prices, results and filings</h2>
      <p>
        Each company page also shows the share price, key numbers and recent filings, all from NSE, and refreshed every
        weekday night after the market&apos;s files are published.
      </p>
      <ul>
        <li>
          <b>Prices</b> are NSE&apos;s official daily closing prices, not live quotes. Prices before a split or bonus
          are adjusted so the chart has no false drops. Dotted lines on the chart mark earnings calls; tap one to read
          what was promised on that call.
        </li>
        <li>
          <b>Key numbers</b> such as profit, growth, margin and P/E are computed from the results the company filed
          with NSE (XBRL). Market cap is shares on issue times the last close. Nothing is estimated: a number that
          can&apos;t be computed from filings is left out.
        </li>
        <li>
          <b>Filings</b> are the company&apos;s own announcements to NSE, each linking the original document. Routine
          paperwork is left out. Resignations, auditor changes, pledges, credit ratings and regulatory orders are
          marked &ldquo;worth a look&rdquo; by fixed rules, not by a model.
        </li>
        <li>
          <b>Signals</b> are four plain facts: how many checkable promises management kept, how the price moved
          against the Nifty 50, whether delivery is above or below usual, and any filings worth a look. They are not
          a rating.
        </li>
      </ul>
      <p>
        When a company files a new earnings-call transcript or new results, FINN checks its promises again
        overnight, one company a night.
      </p>

      <h2>What to keep in mind</h2>
      <p>
        FINN is in beta. Sorting sentences is automated and can be wrong, which is why every verdict shows the exact
        quote, the page, and the source. Segment targets, such as one business line&apos;s margin, can&apos;t be
        checked against company-wide filings and stay unverifiable unless management reports them. Nothing here is
        investment advice.
      </p>
    </article>
  );
}
