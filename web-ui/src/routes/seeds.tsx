import { createFileRoute, Outlet } from "@tanstack/react-router";
import {
  useIsLeafRoute,
  WorkspaceLink,
  WorkspacePlaceholder,
} from "./-workspacePlaceholders";

export const Route = createFileRoute("/seeds")({
  component: SeedsRoute,
});

function SeedsRoute() {
  const isLeafRoute = useIsLeafRoute(Route.id);

  if (!isLeafRoute) return <Outlet />;

  return (
    <WorkspacePlaceholder
      kicker="Workspace"
      title="Seeds"
      actions={[
        {
          label: "New seed lot",
          link: <WorkspaceLink to="/seeds/new">New seed lot</WorkspaceLink>,
        },
      ]}
    />
  );
}
