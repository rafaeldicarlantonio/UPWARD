interface UncertaintyPanelProps {
  text: string;
}

export function UncertaintyPanel({ text }: UncertaintyPanelProps) {
  if (!text?.trim()) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-3">
        <h3 className="text-base font-medium text-slate-900">Uncertainty & Caveats</h3>
      </header>
      <p className="text-sm leading-relaxed text-slate-700">{text}</p>
    </section>
  );
}

