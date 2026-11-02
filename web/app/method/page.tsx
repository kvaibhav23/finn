import type { Metadata } from "next";

import { VerdictMark } from "@/components/VerdictMark";
import type { Verdict } from "@/lib/types";

export const metadata: Metadata = { title: "How it works" };

const RULES: [Verdict, string][] = [
  ["Kept", "The deadline has passed and the filed result met the target. Beating a margin or growth band counts; overspending a budget does not."],
  ["Missed", "The deadline has passed and the result fell short, or management said it was delayed."],
  ["On track", "Not due yet, and the results so far already meet the target."],
  ["Revised", "Not due yet, and a later call changed the number or the deadline."],
  ["Pending", "Not due yet, or no deadline was given, and there is nothing to judge so far."],
  ["Dropped", "Never mentioned again in any later call FINN read."],
  ["Unverifiable", "Due, but there is no filed figure and management never said what happened."],
];

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
