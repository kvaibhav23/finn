// Subscribers in Upstash Redis, over its REST API (no client library):
//   sub:<token>              JSON Subscriber
//   addr:<channel>:<address> token
//   sym:<SYMBOL>             set of tokens following the company
//   sent:<event>:<token>     marks an alert as sent (30 days), so a repeated dispatch sends nothing twice
//   rl:<ip>                  sign-ups from one address this hour

import { randomBytes } from "node:crypto";

import { redisConfig } from "./config";
import type { Channel, Subscriber } from "./core";

type Cmd = (string | number)[];

async function pipeline(cmds: Cmd[]): Promise<unknown[]> {
  const { url, token } = redisConfig();
  const r = await fetch(`${url}/pipeline`, {
    method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(cmds), cache: "no-store",
  });
  if (!r.ok) throw new Error(`redis ${r.status}`);
  const out = (await r.json()) as { result?: unknown; error?: string }[];
  const err = out.find((x) => x.error);
  if (err) throw new Error(`redis: ${err.error}`);
  return out.map((x) => x.result);
}

const one = async (cmd: Cmd) => (await pipeline([cmd]))[0];

export const newToken = () => randomBytes(24).toString("base64url");

export async function getSub(token: string): Promise<Subscriber | null> {
  if (!/^[\w-]{20,64}$/.test(token)) return null;
  const v = await one(["GET", `sub:${token}`]);
  return typeof v === "string" ? (JSON.parse(v) as Subscriber) : null;
}

export async function tokenFor(channel: Channel, address: string): Promise<string | null> {
  const v = await one(["GET", `addr:${channel}:${address}`]);
  return typeof v === "string" ? v : null;
}

export async function saveSub(token: string, sub: Subscriber): Promise<void> {
  await pipeline([
    ["SET", `sub:${token}`, JSON.stringify(sub)],
    ["SET", `addr:${sub.channel}:${sub.address}`, token],
    ...sub.symbols.map((s): Cmd => ["SADD", `sym:${s}`, token]),
  ]);
}

export async function deleteSub(token: string, sub: Subscriber): Promise<void> {
  await pipeline([
    ["DEL", `sub:${token}`],
    ["DEL", `addr:${sub.channel}:${sub.address}`],
    ...sub.symbols.map((s): Cmd => ["SREM", `sym:${s}`, token]),
  ]);
}

export async function dropSymbol(token: string, sub: Subscriber, symbol: string): Promise<Subscriber | null> {
  const left = sub.symbols.filter((s) => s !== symbol);
  if (!left.length) {
    await deleteSub(token, sub);
    return null;
  }
  const next = { ...sub, symbols: left };
  await pipeline([["SET", `sub:${token}`, JSON.stringify(next)], ["SREM", `sym:${symbol}`, token]]);
  return next;
}

export async function followers(symbol: string): Promise<{ token: string; sub: Subscriber }[]> {
  const tokens = (await one(["SMEMBERS", `sym:${symbol}`])) as string[] | null;
  if (!tokens?.length) return [];
  const subs = (await one(["MGET", ...tokens.map((t) => `sub:${t}`)])) as (string | null)[];
  return tokens.flatMap((token, i) => (subs[i] ? [{ token, sub: JSON.parse(subs[i]!) as Subscriber }] : []));
}

/** True the first time; false if this alert already went to this subscriber. */
export async function markSent(eventId: string, token: string): Promise<boolean> {
  return (await one(["SET", `sent:${eventId}:${token}`, "1", "NX", "EX", 30 * 86_400])) === "OK";
}

/** Counts sign-ups from one IP; true while under `limit` an hour. */
export async function underLimit(ip: string, limit = 10): Promise<boolean> {
  const [n] = (await pipeline([["INCR", `rl:${ip}`], ["EXPIRE", `rl:${ip}`, 3600, "NX"]])) as number[];
  return n <= limit;
}
