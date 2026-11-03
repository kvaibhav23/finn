import { readFile } from "node:fs/promises";
import path from "node:path";

import type { Digest, IndexEntry, Ledger, Market, MarketDay, PortfolioEntry } from "./types";

const DATA = path.join(process.cwd(), "public", "data");

// The data files only change with a new deploy (the nightly update commits them), so each server instance reads
// and parses a file once and reuses it, instead of on every page view.
const cache = new Map<string, Promise<unknown>>();

function json<T>(file: string): Promise<T | null> {
  if (!cache.has(file)) {
    cache.set(file, readFile(path.join(DATA, file), "utf8").then((s) => JSON.parse(s) as T, () => null));
  }
  return cache.get(file) as Promise<T | null>;
}

export const getIndex = async () => (await json<IndexEntry[]>("index.json")) ?? [];

/** [symbol, name] for every NSE mainboard listing. */
export const getSymbols = async () => (await json<[string, string][]>("symbols.json")) ?? [];

export async function getLedger(symbol: string): Promise<Ledger | null> {
  if (!/^[A-Z0-9&_-]{1,20}$/.test(symbol)) return null;
  return json<Ledger>(`ledgers/${symbol}.json`);
}

export async function getMarket(symbol: string): Promise<Market | null> {
  if (!/^[A-Z0-9&_-]{1,20}$/.test(symbol)) return null;
  return json<Market>(`market/${symbol}.json`);
}

/** The mock portfolio FINN watches every trading day (finn/portfolio.py). */
export const getPortfolio = async () => (await json<PortfolioEntry[]>("portfolio.json")) ?? [];

/** Every non-routine filing across the watched companies, last 30 days, ranked (scripts/build_web_data.py). */
export const getDigest = async () => json<Digest>("digest.json");

/** The Nifty 50's last session and the biggest movers on FINN (written by scripts/build_web_data.py). */
export const getMarketDay = async () => json<MarketDay>("market.json");

export async function companyName(symbol: string): Promise<string | null> {
  const hit = (await getSymbols()).find(([s]) => s === symbol);
  return hit ? hit[1] : null;
}
