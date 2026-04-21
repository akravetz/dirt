import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import { TopBar } from "@/ui/TopBar";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootComponent,
});

function RootComponent() {
  return (
    <div className="flex min-h-screen flex-col bg-paper font-sans text-ink">
      <TopBar />
      <Outlet />
    </div>
  );
}
