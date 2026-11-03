// Sending: email through Resend's HTTP API, WhatsApp through Meta's Cloud API. Both use pre-agreed formats:
// WhatsApp business messages must use templates approved in Meta's WhatsApp Manager.

import { emailConfig, whatsappConfig } from "./config";

export async function sendEmail(to: string, subject: string, html: string, text: string, unsubscribe?: string): Promise<void> {
  const { key, from } = emailConfig();
  const headers: Record<string, string> = unsubscribe
    ? { "List-Unsubscribe": `<${unsubscribe}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" }
    : {};
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST", headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from, to: [to], subject, html, text, headers }),
  });
  if (!r.ok) throw new Error(`email ${r.status}`);
}

/** A template message; `params` fill {{1}}, {{2}}, ... in the template body, in order. */
export async function sendWhatsApp(to: string, template: string, params: string[]): Promise<void> {
  const w = whatsappConfig();
  const r = await fetch(`https://graph.facebook.com/v21.0/${w.phoneId}/messages`, {
    method: "POST", headers: { Authorization: `Bearer ${w.token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      messaging_product: "whatsapp", to, type: "template",
      template: {
        name: template, language: { code: w.templateLang },
        components: [{ type: "body", parameters: params.map((text) => ({ type: "text", text: text.slice(0, 900) })) }],
      },
    }),
  });
  if (!r.ok) throw new Error(`whatsapp ${r.status}`);
}
