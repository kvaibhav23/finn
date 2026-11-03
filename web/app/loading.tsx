// Shown the moment a link is tapped, while the next page is built: the old page never just sits there.
export default function Loading() {
  return (
    <div className="skeleton" aria-busy="true">
      <span className="sk sk-title" />
      <span className="sk sk-line" />
      <span className="sk sk-line short" />
      <span className="sk sk-block" />
      <span className="sk sk-block" />
    </div>
  );
}
