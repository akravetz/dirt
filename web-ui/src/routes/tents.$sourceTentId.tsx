import { createFileRoute, Outlet } from "@tanstack/react-router";
import {
  useIsLeafRoute,
  WorkspaceLink,
  WorkspacePlaceholder,
} from "./-workspacePlaceholders";

export const Route = createFileRoute("/tents/$sourceTentId")({
  component: TentRoute,
});

function TentRoute() {
  const { sourceTentId } = Route.useParams();
  const isLeafRoute = useIsLeafRoute(Route.id);

  if (!isLeafRoute) return <Outlet />;

  return (
    <WorkspacePlaceholder
      kicker="Tent"
      title={`Tent ${sourceTentId}`}
      facts={[{ label: "Source tent", value: sourceTentId }]}
      actions={[
        { label: "Tents", link: <WorkspaceLink to="/tents">Tents</WorkspaceLink> },
      ]}
    />
  );
}
