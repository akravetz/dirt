import type { QueryClient } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  Outlet,
  useRouterState,
} from "@tanstack/react-router";
import { createDirtApiClient } from "@/api-client";
import { TopBar } from "@/ui/TopBar";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootComponent,
});

const api = createDirtApiClient();

// The pre-auth /login screen owns the full viewport (botanical
// split-screen) and has no app chrome — suppress the TopBar when the
// router is sitting on it. Dashboard / Live / Wiki all keep the TopBar
// and get the Day N · strain grow-context summary from /api/grow/current.
function RootComponent() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isLogin = pathname === "/login";

  // Cached query: one fetch shared by every non-login route. Disabled
  // on /login to avoid firing while unauthenticated (the call would
  // 401 → router redirect loop).
  const { data } = useQuery({
    queryKey: ["grow.current"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/grow/current");
      if (error) throw error;
      return data;
    },
    enabled: !isLogin,
  });

  const growContext = data ? { dayNumber: data.day_number, strain: data.strain } : null;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-paper font-sans text-ink">
      {isLogin ? null : <TopBar growContext={growContext} />}
      <Outlet />
    </div>
  );
}
