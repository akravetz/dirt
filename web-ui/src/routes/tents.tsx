import { createFileRoute, Outlet } from "@tanstack/react-router";
import { DefaultTentRedirect } from "@/features/tents/TentsWorkspace";
import { useIsLeafRoute } from "./-leafRoute";

export const Route = createFileRoute("/tents")({
  component: TentsRoute,
});

function TentsRoute() {
  return useIsLeafRoute(Route.id) ? <DefaultTentRedirect /> : <Outlet />;
}
