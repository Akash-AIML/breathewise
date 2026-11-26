import React from "react";
import Link from "next/link";
import { Wind, MessageSquare } from "lucide-react";

export const Navbar = () => {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/90">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-2.5 text-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2 dark:text-emerald-400"
          aria-label="BreatheWise Home"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-700 text-white shadow-sm">
            <Wind className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">
              BreatheWise
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-400 -mt-1">
              Urban Air Quality Intelligence
            </span>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600 dark:text-slate-300" aria-label="Main Navigation">
          <Link
            href="#assistant"
            className="flex items-center gap-1.5 rounded-md bg-emerald-50 px-3 py-1.5 text-emerald-800 font-semibold hover:bg-emerald-100 transition-colors dark:bg-emerald-950 dark:text-emerald-300"
          >
            <MessageSquare className="h-4 w-4" aria-hidden="true" />
            AI Assistant
          </Link>
        </nav>
      </div>
    </header>
  );
};

