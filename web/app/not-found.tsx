import Link from "next/link";

export default function NotFound() {
  return (
    <section className="prose">
      <h1>No NSE company by that symbol</h1>
      <p className="lede">
        FINN covers companies listed on the NSE main board. Check the symbol, or search by company name.
      </p>
      <p><Link href="/">Search companies</Link></p>
    </section>
  );
}
