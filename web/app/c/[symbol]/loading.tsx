// The company page's outline (name, price, key figures, sections) while its data loads.
export default function Loading() {
  return (
    <div className="skeleton" aria-busy="true">
      <span className="sk sk-title" />
      <span className="sk sk-price" />
      <span className="sk sk-board" />
      <span className="sk sk-tabs" />
      <div className="sk-grid">
        <span className="sk sk-tile" />
        <span className="sk sk-tile" />
        <span className="sk sk-tile" />
        <span className="sk sk-tile" />
      </div>
    </div>
  );
}
