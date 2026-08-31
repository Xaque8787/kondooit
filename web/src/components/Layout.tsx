import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? "bg-ink-800 text-ink-100"
        : "text-ink-400 hover:text-ink-100 hover:bg-ink-800/50"
    }`;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-50 bg-ink-950/95 backdrop-blur border-b border-ink-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-8">
              <NavLink to="/" className="flex items-center gap-2">
                <span className="text-xl font-bold tracking-tight text-ink-100">
                  Kondooit
                </span>
              </NavLink>
              <nav className="flex items-center gap-1">
                <NavLink to="/movies" className={navLinkClass}>
                  Movies
                </NavLink>
                <NavLink to="/series" className={navLinkClass}>
                  TV Shows
                </NavLink>
                <NavLink to="/providers" className={navLinkClass}>
                  Providers
                </NavLink>
              </nav>
            </div>
            <div className="flex items-center gap-4">
              {user && (
                <div className="flex items-center gap-3">
                  <span className="text-sm text-ink-400 hidden sm:inline">
                    {user.username}
                  </span>
                  <button onClick={handleLogout} className="btn-ghost text-sm">
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-ink-800 py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-ink-500">
          Kondooit v0.0.1
        </div>
      </footer>
    </div>
  );
}
