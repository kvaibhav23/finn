import type { NextConfig } from "next";

const config: NextConfig = {
  // Ledger JSON is read from public/data at request time by the company page and the API routes.
  outputFileTracingIncludes: {
    "/c/[symbol]": ["./public/data/**/*"],
    "/api/analyze": ["./public/data/index.json", "./public/data/symbols.json"],
    "/api/status": ["./public/data/index.json"],
  },
  poweredByHeader: false,
};

export default config;
