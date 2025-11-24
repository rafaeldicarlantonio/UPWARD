'use client';

import { useId } from 'react';
import { useMode } from '@/app/context/mode-context';
import { Mode } from '@/lib/types';

const MODE_OPTIONS: { value: Mode; label: string; helper: string }[] = [
  { value: 'public', label: 'Public', helper: 'Condensed evidence, minimal process.' },
  { value: 'scholar', label: 'Scholar', helper: 'Full epistemic view with REDO trace.' },
  { value: 'staff', label: 'Staff', helper: 'Scholar view plus governance controls.' },
];

export function ModeSelector() {
  const { mode, setMode } = useMode();
  const selectId = useId();

  return (
    <div className="flex flex-col gap-1 text-sm text-slate-600">
      <label htmlFor={selectId} className="font-medium text-slate-700">
        Mode
      </label>
      <div className="relative">
        <select
          id={selectId}
          value={mode}
          onChange={(event) => setMode(event.target.value as Mode)}
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-400"
        >
          {MODE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-500">
          <svg
            className="h-4 w-4"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              d="M6 8l4 4 4-4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>
      <p className="text-xs text-slate-500">
        {MODE_OPTIONS.find((option) => option.value === mode)?.helper}
      </p>
    </div>
  );
}

