// A price line with no axes: the shape of the year at a glance. The numbers are always printed next to it.
export function Sparkline({ values, width = 120, height = 32, className = "spark" }:
  { values: number[]; width?: number; height?: number; className?: string }) {
  if (values.length < 2) return null;
  const lo = Math.min(...values), hi = Math.max(...values);
  const span = hi - lo || 1;
  const pts = values.map((v, i) =>
    `${((i / (values.length - 1)) * width).toFixed(1)},${(2 + (1 - (v - lo) / span) * (height - 4)).toFixed(1)}`);
  const down = values[values.length - 1] < values[0];
  return (
    <svg className={`${className}${down ? " down" : " up"}`} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
         width={width} height={height} aria-hidden focusable="false">
      <polyline points={pts.join(" ")} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
