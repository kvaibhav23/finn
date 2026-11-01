# Spike 08: are NSE sources reachable from cloud servers?

**Status: local and GitHub Actions columns done. Other hosts are waiting on manual runs.**

**Verdict:**
- **Local (residential):** PASS, 7/7 data checks.
- **Cloud, GitHub Actions `ubuntu-latest` (Azure, github-hosted):** PASS, 7/7 data checks, identical to local (2 runs, 2026-11-01 17:43 and 18:13 IST).
- **Other cloud providers and regions:** not run yet. This spike decides FINN's deployment.

Run: `python spikes/08_cloud_reachability/run.py --env <label>`

## Verdict
**(A) Everything works from the cloud.** On GitHub's Azure-hosted runner, the static `nsearchives` files and all three cookie-gated `/api/` calls returned 200 with real data, identical to the local Mac. Caveats: two runs from one datacentre; steady scheduled polling and Indian regions are untested.

## Method
- **Same requests everywhere.** The headers are imported unchanged from `spikes/common.py`, as used by spikes 01–07. Only the network differs.
- **One call per check.**
  - The single exception: if a `/api/` call gets 401/403, re-warm cookies once per run and repeat that call once. Both attempts are recorded.
  - The bhavcopy check (a2) steps back one weekday **only on 404** (weekend or holiday), up to 4 times. Each step is a different file.
- **No header tuning, proxies or IP rotation.** A block is recorded as the result.
- **The `data/raw` cache is bypassed on purpose:** a cache hit would be a false "reachable". Requests are still spaced at least 1.1 s apart, about 8–12 per run.
- **Verdicts:**
  - `OK`: 200 and the expected content (CSV header, `PK` zip magic, XML, `%PDF-`, JSON shape).
  - `BAD_BODY`: 200 but the wrong content, e.g. a challenge page.
  - `BLOCKED`: 401/403.
  - `NOT_FOUND`, `HTTP_<code>`, `TIMEOUT` (20 s), `CONN_ERR`.
  - JSON responses also record an item count, because an empty list would be weak evidence.
- **Recognising a block:** Akamai's block page is `<TITLE>Access Denied</TITLE> … Reference #…`. The first 200 bytes of every failure are recorded.

## Results
Cell format: `status verdict · latency (· items)`. Columns marked *pending* are for runs you do manually; paste the column the script prints.

| id | check | local-mac (residential) | github-ubuntu-latest | aws-ap-south-1 | gcp-asia-south1 | indian-vps | other (non-India) |
|---|---|---|---|---|---|---|---|
| a1 | `nsearchives` EQUITY_L.csv | 200 OK · 533 ms | 200 OK · 353 ms | | | | |
| a2 | `nsearchives` UDiFF bhavcopy (last trading day) | 200 OK · 283 ms (2026-10-30) | 200 OK · 212 ms (2026-10-30) | | | | |
| a3 | `nsearchives` known XBRL (TCS Q2 FY27) | 200 OK · 99 ms | 200 OK · 220 ms | | | | |
| a4 | `nsearchives` known PDF (RIL, 239 KB) | 200 OK · 187 ms | 200 OK · 208 ms | | | | |
| b0 | `www` home-page warm-up (recorded only) | 403 BLOCKED · 319 ms | 403 BLOCKED · 77 ms | | | | |
| b1 | `/api/corporate-announcements` (RELIANCE, 7 days) | 200 OK · 911 ms · 8 items | 200 OK · 672 ms · 8 items | | | | |
| b2 | `/api/integrated-filing-results` (TCS, financials) | 200 OK · 179 ms · 14 items | 200 OK · 272 ms · 14 items | | | | |
| b3 | `/api/annual-reports` (TCS) | 200 OK · 187 ms · 17 items | 200 OK · 284 ms · 17 items | | | | |
| | run time (IST) | 2026-11-01 05:08 | 2026-11-01 17:43 (run 41305423895); repeated 18:13 (run 41307837602), identical verdicts | | | | |
| | re-warm used? | no | no | | | | |

### Local notes (local-mac, 2026-11-01 05:07 and 05:08 IST, two runs, identical verdicts)
- **The home page returns 403 "Access Denied" from a residential connection too**, yet every `/api/` call succeeds after it.
  - In these runs, the warm-up set only the `AKA_A2` cookie. Spikes 02–07 saw 5 Akamai cookies (`_abck, ak_bmsc, bm_sv, bm_sz, AKA_A2`).
  - Whether the API needs the warm-up at all wasn't tested; that would be probing the bot defences.
- **The first run used TCS for b1.** It returned `[]` (200 OK, 2 bytes), because TCS genuinely had no filings that week. b1 was switched to RELIANCE (8 items) so a success can't be confused with an empty soft-block.

### GitHub Actions notes (run 41305423895, 2026-11-01 17:43 IST)
- **Runner:** `Linux-7.0.0-1017-azure-x86_64`, `RUNNER_ENVIRONMENT=github-hosted`, Python 3.12.15. The Azure region isn't exposed or chosen.
- **Same pattern as local:**
  - the home page returns 403 with only the `AKA_A2` cookie;
  - all three APIs return 200 with the same item counts (8 / 14 / 17);
  - every static file returns 200 with byte-identical sizes.
- **Second run** (41307837602, 18:13 IST, 30 min later): identical verdicts and item counts. Latencies were 104–729 ms (a1 114 ms, b1 729 ms).
- **Scope:** this is two runs, 30 minutes apart, from one datacentre. Akamai policy can vary by IP reputation, region and load. Treat it as "not blocked by default from a major cloud", not a guarantee. Sustained or scheduled polling from cloud IPs is untested.

### Failure excerpts
- **local-mac b0 and github-ubuntu-latest b0** `403` (identical bodies): `<HTML><HEAD><TITLE>Access Denied</TITLE></HEAD><BODY><H1>Access Denied</H1> You don't have permission to access "http://www.nseindia.com/" on this server.<P> Reference…`

## How to run on another host
```bash
git clone <repo> finn && cd finn
python3 -m venv .venv && . .venv/bin/activate && pip install requests   # Python 3.10+
python spikes/08_cloud_reachability/run.py --env aws-ap-south-1
```
- **Label convention:** `<provider>-<region>[-<note>]`, e.g. `aws-ap-south-1`, `gcp-asia-south1`, `hetzner-fsn1`, `do-blr1`.
- **Output:** the script prints a ready-to-paste column and writes full detail (headers, first 200 bytes of failures, cookies) to `data/reachability/<label>_<utc>.json`.
- **GitHub Actions:** push the repo, then Actions → "NSE reachability" → Run workflow (optional `env_label` input).
  - The results appear in the job summary and as the `reachability-<label>-<run_id>` artifact.
  - The runners are Azure-hosted; the region can't be chosen.

## Deployment implications (fill in once the cloud columns exist; no conclusions yet)
| outcome from a cloud host | implication |
|---|---|
| a1–a4 OK and b1–b3 OK | Single cloud deployment for the whole data layer. |
| a1–a4 OK, b1–b3 BLOCKED | Archives, bhavcopy and XBRL/PDF downloads can run in the cloud. The cookie-gated pieces need a legitimate alternative:<br>- filings discovery (b1)<br>- the integrated-filing listing (b2)<br>- the annual-report listing (b3)<br>Candidates: an Indian-region host *if* it passes, licensed NSE data / a vendor feed, or company and BSE sources. **No proxies or IP rotation.** |
| Indian region OK, other regions BLOCKED | Pin the fetcher to an Indian region; the rest of FINN can live anywhere. |
| a1–a4 BLOCKED | The data layer can't be cloud-hosted as-is; licensed data becomes a requirement. |

Note: `nsearchives` file URLs come *from* the `/api/` listings (filings, XBRL, annual reports). Static access alone covers only the files whose URLs are predictable (EQUITY_L, bhavcopy).
