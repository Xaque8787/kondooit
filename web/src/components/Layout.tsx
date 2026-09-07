import { useState, useRef, useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export function Layout() {
  const { activeProfile, logout, clearProfile } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleSwitchProfile = () => {
    clearProfile();
    navigate("/profiles");
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
            <div className="flex items-center gap-3">
              {activeProfile && (
                <div className="relative" ref={menuRef}>
                  <button
                    onClick={() => setMenuOpen((o) => !o)}
                    className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-ink-800/50 transition-colors"
                  >
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold text-white"
                      style={{ backgroundColor: activeProfile.avatar_color }}
                    >
                      {activeProfile.display_name.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-sm text-ink-300 hidden sm:inline">
                      {activeProfile.display_name}
                    </span>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-ink-500">
                      <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                    </svg>
                  </button>

                  {menuOpen && (
                    <div className="absolute right-0 mt-2 w-48 bg-ink-900 border border-ink-700 rounded-xl shadow-xl overflow-hidden z-50">
                      <button
                        onClick={() => { setMenuOpen(false); navigate("/profile/settings"); }}
                        className="w-full px-4 py-2.5 text-left text-sm text-ink-300 hover:bg-ink-800 hover:text-ink-100 transition-colors flex items-center gap-2"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-ink-500">
                          <path fillRule="evenodd" d="M7.84 1.804A1 1 0 018.82 1h2.36a1 1 0 01.98.804l.331 1.652a6.993 6.993 0 011.929 1.115l1.598-.54a1 1 0 011.186.447l1.18 2.044a1 1 0 01-.205 1.251l-1.267 1.113a7.047 7.047 0 010 2.228l1.267 1.113a1 1 0 01.206 1.25l-1.18 2.045a1 1 0 01-1.187.447l-1.598-.54a6.993 6.993 0 01-1.929 1.115l-.33 1.652a1 1 0 01-.98.804H8.82a1 1 0 01-.98-.804l-.331-1.652a6.993 6.993 0 01-1.929-1.115l-1.598.54a1 1 0 01-1.186-.447l-1.18-2.044a1 1 0 01.205-1.251l1.267-1.114a7.05 7.05 0 010-2.227L1.821 7.773a1 1 0 01-.206-1.25l1.18-2.045a1 1 0 011.187-.447l1.598.54A6.993 6.993 0 017.51 3.456l.33-1.652zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
                        </svg>
                        Profile Settings
                      </button>
                      <button
                        onClick={() => { setMenuOpen(false); handleSwitchProfile(); }}
                        className="w-full px-4 py-2.5 text-left text-sm text-ink-300 hover:bg-ink-800 hover:text-ink-100 transition-colors flex items-center gap-2"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-ink-500">
                          <path d="M10 8a3 3 0 100-6 3 3 0 000 6zM3.465 14.493a1.23 1.23 0 00.41 1.412A9.957 9.957 0 0010 18c2.31 0 4.438-.784 6.131-2.1.43-.333.604-.903.408-1.41a7.002 7.002 0 00-13.074.003z" />
                        </svg>
                        Switch Profile
                      </button>
                      <div className="border-t border-ink-700" />
                      <button
                        onClick={() => { setMenuOpen(false); handleLogout(); }}
                        className="w-full px-4 py-2.5 text-left text-sm text-ink-300 hover:bg-ink-800 hover:text-ink-100 transition-colors flex items-center gap-2"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-ink-500">
                          <path fillRule="evenodd" d="M3 4.25A2.25 2.25 0 015.25 2h5.5A2.25 2.25 0 0113 4.25v2a.75.75 0 01-1.5 0v-2a.75.75 0 00-.75-.75h-5.5a.75.75 0 00-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 00.75-.75v-2a.75.75 0 011.5 0v2A2.25 2.25 0 0110.75 18h-5.5A2.25 2.25 0 013 15.75V4.25z" clipRule="evenodd" />
                          <path fillRule="evenodd" d="M6 10a.75.75 0 01.75-.75h9.546l-1.048-.943a.75.75 0 111.004-1.114l2.5 2.25a.75.75 0 010 1.114l-2.5 2.25a.75.75 0 11-1.004-1.114l1.048-.943H6.75A.75.75 0 016 10z" clipRule="evenodd" />
                        </svg>
                        Sign Out
                      </button>
                    </div>
                  )}
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
          Kondooit v0.0.2
        </div>
      </footer>
    </div>
  );
}
