import { createFileRoute, Outlet } from "@tanstack/react-router";
import {
  useIsLeafRoute,
  WorkspaceLink,
  WorkspacePlaceholder,
} from "./-workspacePlaceholders";

export const Route = createFileRoute("/seeds/$seedLotId")({
  component: SeedLotRoute,
});

function SeedLotRoute() {
  const { seedLotId } = Route.useParams();
  const isLeafRoute = useIsLeafRoute(Route.id);

  if (!isLeafRoute) return <Outlet />;

  return (
    <WorkspacePlaceholder
      kicker="Seed lot"
      title={seedLotId}
      facts={[{ label: "Seed lot", value: seedLotId }]}
      actions={[
        { label: "Seeds", link: <WorkspaceLink to="/seeds">Seeds</WorkspaceLink> },
      ]}
    />
  );
}
