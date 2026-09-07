import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { User, ProfileBrief } from "./types";
import { api } from "./api";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  activeProfile: ProfileBrief | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  bootstrap: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  selectProfile: (profile: ProfileBrief) => void;
  clearProfile: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    localStorage.getItem("kondooit_token"),
  );
  const [activeProfile, setActiveProfile] = useState<ProfileBrief | null>(() => {
    const stored = localStorage.getItem("kondooit_profile");
    return stored ? JSON.parse(stored) : null;
  });
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const u = await api.me();
      setUser(u);
      if (activeProfile) {
        const still = u.profiles.find((p) => p.id === activeProfile.id);
        if (!still) {
          setActiveProfile(null);
          localStorage.removeItem("kondooit_profile");
        }
      }
    } catch {
      localStorage.removeItem("kondooit_token");
      localStorage.removeItem("kondooit_profile");
      setToken(null);
      setUser(null);
      setActiveProfile(null);
    }
  }, [activeProfile]);

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
    localStorage.removeItem("kondooit_profile");
    setToken(null);
    setUser(null);
    setActiveProfile(null);
  };

  const selectProfile = (profile: ProfileBrief) => {
    setActiveProfile(profile);
    localStorage.setItem("kondooit_profile", JSON.stringify(profile));
  };

  const clearProfile = () => {
    setActiveProfile(null);
    localStorage.removeItem("kondooit_profile");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        activeProfile,
        loading,
        login,
        bootstrap,
        logout,
        selectProfile,
        clearProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
