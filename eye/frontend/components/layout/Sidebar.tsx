"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", icon: "▦", label: "dashboard" },
  { href: "/new", icon: "＋", label: "new_analysis" },
  { href: "/report", icon: "▤", label: "report" },
  { href: "/qa", icon: "💬", label: "qa_session" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-[220px] min-h-screen bg-bg-page p-6 flex flex-col gap-1">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-3 pb-8">
        <span className="text-accent-orange text-2xl font-mono">◉</span>
        <span className="font-[family-name:var(--font-display)] text-text-primary text-xl font-bold tracking-wide">
          ComadEye
        </span>
      </Link>

      {/* Navigation */}
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center px-3 py-2.5 rounded-lg font-mono text-sm transition-colors ${
                isActive
                  ? "bg-bg-elevated text-accent-orange"
                  : "text-text-secondary hover:bg-bg-elevated/50 hover:text-text-primary"
              }`}
            >
              <span className="mr-2.5 text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
