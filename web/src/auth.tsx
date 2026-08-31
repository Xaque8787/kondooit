import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { User } from "./types";
import { api } from "./api";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  bootstrap: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    localStorage.getItem("kondooit_token"),
  );
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const u = await api.me();
      setUser(u);
    } catch {
      localStorage.removeItem("kondooit_token");
      setToken(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    if (token) {
      fetchUser().finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [token, fetchUser]);

  const login = async (username: string, password: string) => {
    const res = await api.login(username, password);
    localStorage.setItem("kondooit_token", res.access_token);
    setToken(res.access_token);
    await fetchUser();
  };

  const bootstrap = async (
    username: string,
    email: string,
    password: string,
  ) => {
    const res = await api.bootstrap(username, email, password);
    localStorage.setItem("kondooit_token", res.access_token);
    setToken(res.access_token);
    await fetchUser();
  };

  const logout = () => {
    localStorage.removeItem("kondooit_token");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, bootstrap, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
