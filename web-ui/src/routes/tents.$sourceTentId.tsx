import { createFileRoute, Outlet } from "@tanstack/react-router";
import { TentsWorkspace } from "@/features/tents/TentsWorkspace";
import { useIsLeafRoute } from "./-workspacePlaceholders";

export const Route = createFileRoute("/tents/$sourceTentId")({
  component: TentRoute,
});

function TentRoute() {
  const { sourceTentId } = Route.useParams();
  const isLeafRoute = useIsLeafRoute(Route.id);

  if (!isLeafRoute) return <Outlet />;

  return <TentsWorkspace sourceTentId={sourceTentId} />;
}
