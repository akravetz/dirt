import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  Outlet,
  useRouterState,
} from "@tanstack/react-router";
import { TopBar } from "@/ui/TopBar";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootComponent,
});

// The pre-auth /login screen owns the full viewport (botanical
// split-screen) and has no app chrome — suppress the TopBar when the
// router is sitting on it. Dashboard / Live / Wiki all keep the TopBar.
function RootComponent() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isLogin = pathname === "/login";
  return (
    <div className="flex min-h-screen flex-col bg-paper font-sans text-ink">
      {isLogin ? null : <TopBar />}
      <Outlet />
    </div>
  );
}
