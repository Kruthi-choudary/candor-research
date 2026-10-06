import { NavLink, Outlet } from "react-router-dom";
import { Home, BarChart3 } from "lucide-react";
import { Logo } from "./Logo";

const NAV_ITEMS = [
  { to: "/app", label: "Home", icon: Home, end: true },
  { to: "/app/evaluation", label: "Evaluation", icon: BarChart3, end: false },
];

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-base">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border px-4 py-5">
        <div className="px-2 pb-6">
          <Logo />
        </div>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-mint/10 text-mint"
                    : "text-text-muted hover:bg-raised hover:text-text"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-2 pt-6 text-xs text-text-faint">
          Candor pipeline v1.0 · local demo
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
