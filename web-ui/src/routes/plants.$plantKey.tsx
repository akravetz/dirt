import { createFileRoute, Outlet } from "@tanstack/react-router";
import {
  useIsLeafRoute,
  WorkspaceLink,
  WorkspacePlaceholder,
} from "./-workspacePlaceholders";

export const Route = createFileRoute("/plants/$plantKey")({
  component: PlantRoute,
});

function PlantRoute() {
  const { plantKey } = Route.useParams();
  const isLeafRoute = useIsLeafRoute(Route.id);

  if (!isLeafRoute) return <Outlet />;

  return (
    <WorkspacePlaceholder
      kicker="Plant"
      title={plantKey}
      facts={[{ label: "Plant key", value: plantKey }]}
      actions={[
        { label: "Plants", link: <WorkspaceLink to="/plants">Plants</WorkspaceLink> },
      ]}
    />
  );
}
