export default function ACarregar() {
  return (
    <div aria-busy="true" aria-live="polite" className="animate-pulse space-y-4">
      <span className="sr-only">A carregar…</span>
      <div className="h-8 w-48 rounded-lg bg-superficie-2" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="h-24 rounded-[var(--radius-cartao)] bg-superficie-2" />
        ))}
      </div>
      <div className="h-64 rounded-[var(--radius-cartao)] bg-superficie-2" />
    </div>
  );
}
