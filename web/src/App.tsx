import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { SetupPage } from "./pages/SetupPage";
import { ProfileSelectPage } from "./pages/ProfileSelectPage";
import { DashboardPage } from "./pages/DashboardPage";
import { MoviesPage } from "./pages/MoviesPage";
import { MovieDetailPage } from "./pages/MovieDetailPage";
import { SeriesPage } from "./pages/SeriesPage";
import { SeriesDetailPage } from "./pages/SeriesDetailPage";
import { DiscoverySectionPage } from "./pages/DiscoverySectionPage";
import { EpisodeDetailPage } from "./pages/EpisodeDetailPage";
import { ProvidersPage } from "./pages/ProvidersPage";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, activeProfile, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-ink-700 border-t-brand-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!activeProfile) {
    return <Navigate to="/profiles" replace />;
  }

  return <>{children}</>;
}

function PublicRoute({ children }: { children: ReactNode }) {
  const { user, activeProfile, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-ink-700 border-t-brand-500 rounded-full animate-spin" />
      </div>
    );
  }
  if (user && activeProfile) {
    return <Navigate to="/" replace />;
  }
  if (user && !activeProfile) {
    return <Navigate to="/profiles" replace />;
  }
  return <>{children}</>;
}

function ProfileRoute({ children }: { children: ReactNode }) {
  const { user, activeProfile, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-ink-700 border-t-brand-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (activeProfile) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/setup"
        element={
          <PublicRoute>
            <SetupPage />
          </PublicRoute>
        }
      />
      <Route
        path="/profiles"
        element={
          <ProfileRoute>
            <ProfileSelectPage />
          </ProfileRoute>
        }
      />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/discover/:sectionKey" element={<DiscoverySectionPage />} />
        <Route path="/movies" element={<MoviesPage />} />
        <Route path="/movie/:provider/:id" element={<MovieDetailPage />} />
        <Route path="/series" element={<SeriesPage />} />
        <Route path="/series/:provider/:id" element={<SeriesDetailPage />} />
        <Route path="/series/:provider/:seriesId/season/:season/episode/:episode" element={<EpisodeDetailPage />} />
        <Route path="/providers" element={<ProvidersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
