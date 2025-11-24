'use client';

export function ProcessSidebar() {
  return (
    <aside className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="space-y-2">
        <p className="text-sm font-semibold text-slate-900">Process Trace</p>
        <p className="text-xs text-slate-500">
          Process trace will appear here. Scholar and Staff modes will show Relevate, Evidentiate, Divide, and Ordinate
          panels.
        </p>
      </div>
      <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-xs text-slate-500">
        Waiting for assistant response...
      </div>
    </aside>
  );
}

