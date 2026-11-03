import type { NextConfig } from "next";

const config: NextConfig = {
  // Data JSON is read from public/data at request time by the pages and the API routes.
  outputFileTracingIncludes: {
    "/": ["./public/data/index.json", "./public/data/market.json", "./public/data/ledgers/*.json"],
    "/companies": ["./public/data/index.json", "./public/data/market.json"],
    "/c/[symbol]": ["./public/data/**/*"],
    "/api/analyze": ["./public/data/index.json", "./public/data/symbols.json"],
    "/api/status": ["./public/data/index.json"],
    "/api/alerts/subscribe": ["./public/data/symbols.json"],
    "/api/alerts/dispatch": ["./public/data/symbols.json"],
  },
  poweredByHeader: false,
};

export default config;
