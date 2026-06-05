import { Navigate, Outlet, useLocation } from "react-router-dom";
import { LoadingState } from "@/components/common/LoadingState";
import { useAuth } from "@/app/AuthProvider";

type ProtectedRouteProps = {
  roles?: string[];
};

export function ProtectedRoute({ roles }: ProtectedRouteProps) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.isLoading) {
    return <LoadingState label="Checking your session..." />;
  }

  if (!auth.isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (roles?.length && !auth.hasRole(...roles)) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
