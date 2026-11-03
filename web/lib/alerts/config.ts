// Which alert channels are switched on. Each needs its secrets in the Vercel project settings; without them the
// sign-up form says alerts aren't on yet, and nothing is stored or sent.

const env = (k: string) => process.env[k]?.trim() || "";

export const redisConfig = () => ({
  url: env("KV_REST_API_URL") || env("UPSTASH_REDIS_REST_URL"),
  token: env("KV_REST_API_TOKEN") || env("UPSTASH_REDIS_REST_TOKEN"),
});

export const emailConfig = () => ({ key: env("RESEND_API_KEY"), from: env("ALERTS_FROM_EMAIL") });

export const whatsappConfig = () => ({
  token: env("WHATSAPP_TOKEN"),
  phoneId: env("WHATSAPP_PHONE_NUMBER_ID"),
  verify: env("WHATSAPP_VERIFY_TOKEN"),
  appSecret: env("WHATSAPP_APP_SECRET"),
  alertTemplate: env("WHATSAPP_TEMPLATE_ALERT") || "finn_alert",
  welcomeTemplate: env("WHATSAPP_TEMPLATE_WELCOME") || "finn_welcome",
  templateLang: env("WHATSAPP_TEMPLATE_LANG") || "en",
});

export const siteUrl = () => (env("FINN_SITE_URL") || "https://finn-six-roan.vercel.app").replace(/\/$/, "");
export const alertsSecret = () => env("ALERTS_SECRET");

export function channels(): { email: boolean; whatsapp: boolean } {
  const r = redisConfig(), e = emailConfig(), w = whatsappConfig();
  const store = Boolean(r.url && r.token);
  return { email: store && Boolean(e.key && e.from), whatsapp: store && Boolean(w.token && w.phoneId && w.appSecret) };
}
