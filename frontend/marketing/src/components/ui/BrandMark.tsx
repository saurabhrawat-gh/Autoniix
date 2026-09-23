/* Same mark as the dashboard's AppBrandMark — keeps both properties visually one product. */
export default function BrandMark({ size = 22 }: { size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="bg-brand rounded-md shrink-0 grid place-items-center text-white font-bold select-none"
      style={{
        width: size,
        height: size,
        fontSize: Math.max(10, Math.round(size * 0.52)),
        letterSpacing: "0.01em",
        boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.08)",
      }}
    >
      A
    </span>
  );
}
