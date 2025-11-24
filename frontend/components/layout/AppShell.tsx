'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { ModeSelector } from './ModeSelector';

const NAV_LINKS = [
  { href: '/chat', label: 'Chat' },
  { href: '/upload', label: 'Upload' },
  { href: '/debug', label: 'Debug' },
];

const isActivePath = (pathname: string | null, href: string) => {
  if (!pathname) {
    return false;
  }
  if (href === '/chat') {
    return pathname === '/' || pathname.startsWith('/chat');
  }
  return pathname.startsWith(href);
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Link href="/chat" className="text-lg font-semibold text-slate-900">
              UPWARD Console
            </Link>
            <p className="text-xs text-slate-500">Inspect answers, evidence, hypotheses, and process.</p>
          </div>
          <nav aria-label="Primary" className="flex flex-wrap items-center gap-4 text-sm font-medium text-slate-600">
            {NAV_LINKS.map((link) => {
              const active = isActivePath(pathname, link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-full px-3 py-1 transition-colors ${
                    active
                      ? 'bg-slate-900 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
          <div className="w-full max-w-xs sm:max-w-[220px]">
            <ModeSelector />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}

