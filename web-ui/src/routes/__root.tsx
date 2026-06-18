import type { QueryClient } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  Outlet,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router";
import { createHostedApiClient } from "@/api-client";
import { TopBar } from "@/ui/TopBar";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootComponent,
});

const api = createHostedApiClient();

// Pre-auth /login and the standalone Breeding Logbook route own their full
// viewport chrome. Dashboard / Live / Wiki keep the shared TopBar.
function RootComponent() {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isLogin = pathname === "/login";
  const routeOwnsChrome = isLogin || pathname === "/breeding-logbook";
  const { queryClient } = Route.useRouteContext();

  // Cached query: one fetch shared by every non-login route. Disabled
  // on /login to avoid firing while unauthenticated (the call would
  // 401 -> router redirect loop).
  const authQuery = useQuery({
    queryKey: ["auth.me"],
    queryFn: async () => {
      const { data } = await api.GET("/api/auth/me");
      if (data === undefined) throw new Error("GET /api/auth/me returned no data");
      return data;
    },
    enabled: !isLogin,
    staleTime: 60_000,
  });

  const logout = () => {
    void (async () => {
      try {
        await api.POST("/api/auth/logout");
      } finally {
        queryClient.clear();
        await navigate({ to: "/login" });
      }
    })();
  };

  if (!isLogin && authQuery.isLoading) {
    return (
      <div className="flex h-screen flex-col overflow-hidden bg-paper font-sans text-ink">
        <main className="flex-1 p-6">
          <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
            Checking session…
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-paper font-sans text-ink">
      {routeOwnsChrome ? null : <TopBar growContext={null} onLogout={logout} />}
      <Outlet />
    </div>
  );
}
