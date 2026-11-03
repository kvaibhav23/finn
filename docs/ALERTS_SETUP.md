# Switching on FINN alerts (email and WhatsApp)

The code is deployed and sends nothing until these accounts exist. Each step names who does it.
Secrets go only into Vercel's and GitHub's settings screens, never into the code or a chat.

## 1. Storage for sign-ups: Upstash Redis (free tier), about 5 minutes
1. Vercel → the finn project → **Storage** → **Create Database** → **Upstash for Redis** (Marketplace) → free plan,
   region **Mumbai (ap-south-1)** → connect it to the finn project.
2. Vercel adds `KV_REST_API_URL` and `KV_REST_API_TOKEN` to the project by itself. Nothing to copy.

## 2. Email: Resend (free tier: 3,000 emails a month), about 20 minutes
Resend only sends to other people's inboxes from a domain you own and have verified.
1. Sign up at resend.com → **Domains** → add a domain or subdomain you own (for example `alerts.yourdomain.in`)
   → add the DNS records it shows at your domain registrar → wait for **Verified**.
2. **API Keys** → create a key with "Sending access".
3. Vercel → finn → **Settings → Environment Variables** (Production):
   - `RESEND_API_KEY` = the key
   - `ALERTS_FROM_EMAIL` = `FINN alerts <alerts@alerts.yourdomain.in>`

## 3. WhatsApp: Meta WhatsApp Cloud API, from a day to a few weeks (Meta's review)
1. business.facebook.com → create or choose a Business portfolio → complete **Business verification**.
2. developers.facebook.com → **Create app** → type **Business** → add the **WhatsApp** product.
3. WhatsApp → **API Setup** → add and verify the phone number alerts will come from (it can't already be on the
   WhatsApp app) → note the **Phone number ID**.
4. Create a **System user** in Business settings with the WhatsApp permissions → generate a **permanent token**.
5. **App settings → Basic** → note the **App secret**.
6. WhatsApp Manager → **Message templates** → create two templates, category **Utility**, language **English**:
   - `finn_welcome`, body:
     `You're subscribed to FINN alerts for {{1}}. Facts from NSE filings, not investment advice. Reply STOP to stop.`
   - `finn_alert`, body:
     `{{1}}: {{2}} Details: {{3}} Reply STOP to stop alerts.`
   Wait for both to be **Approved**.
7. WhatsApp → **Configuration** → Webhook:
   - Callback URL: `https://finn-six-roan.vercel.app/api/whatsapp/webhook`
   - Verify token: any long random text you choose (also put it in Vercel below)
   - Subscribe to the **messages** field (this is how a STOP reply unsubscribes someone).
8. Vercel → finn → Environment Variables (Production):
   - `WHATSAPP_TOKEN` = the permanent token
   - `WHATSAPP_PHONE_NUMBER_ID` = the phone number ID
   - `WHATSAPP_APP_SECRET` = the app secret
   - `WHATSAPP_VERIFY_TOKEN` = the verify token from step 7
   Meta charges per business-initiated conversation in India; see Meta's current pricing.

## 4. Let the nightly job hand alerts to the site, about 2 minutes
1. Make a long random secret, for example in Terminal: `openssl rand -hex 32`.
2. Vercel → finn → Environment Variables: `ALERTS_SECRET` = that secret, and `FINN_SITE_URL` =
   `https://finn-six-roan.vercel.app` (or your own domain later).
3. GitHub → kvaibhav23/finn → **Settings → Secrets and variables → Actions**:
   - **Secrets** tab: `ALERTS_SECRET` = the same secret
   - **Variables** tab: `FINN_SITE_URL` = the same URL
4. Vercel → **Deployments** → redeploy the latest, so the new variables take effect.

## Check it works
- A company page shows **Get alerts**; the form offers each channel whose step above is done.
- Email: sign up with your own address → the confirmation email arrives → click it → Settings says alerts are on.
- WhatsApp: sign up with your number → the `finn_welcome` message arrives → reply STOP → you're removed.
- After the next evening or overnight update with a big move or a flagged filing, the GitHub run's
  **Send alerts** step shows how many were sent.

## Legal basics before inviting the public
Alerts carry facts from filings and an unsubscribe in every message, and the sign-up asks for explicit consent.
Before launch, add a privacy notice page and check obligations under India's Digital Personal Data Protection Act,
TRAI rules on commercial messages, and SEBI rules on research and recommendations (FINN gives no buy/sell views).
