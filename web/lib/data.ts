import { readFile } from "node:fs/promises";
import path from "node:path";

import type { IndexEntry, Ledger } from "./types";

const DATA = path.join(process.cwd(), "public", "data");

async function json<T>(file: string): Promise<T | null> {
  try {
    return JSON.parse(await readFile(path.join(DATA, file), "utf8")) as T;
  } catch {
    return null;
  }
}

export const getIndex = async () => (await json<IndexEntry[]>("index.json")) ?? [];

/** [symbol, name] for every NSE mainboard listing. */
export const getSymbols = async () => (await json<[string, string][]>("symbols.json")) ?? [];

export async function getLedger(symbol: string): Promise<Ledger | null> {
  if (!/^[A-Z0-9&_-]{1,20}$/.test(symbol)) return null;
  return json<Ledger>(`ledgers/${symbol}.json`);
}

export async function companyName(symbol: string): Promise<string | null> {
  const hit = (await getSymbols()).find(([s]) => s === symbol);
  return hit ? hit[1] : null;
}
