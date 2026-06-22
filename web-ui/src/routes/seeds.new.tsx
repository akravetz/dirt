import { createFileRoute } from "@tanstack/react-router";
import { WorkspaceLink, WorkspacePlaceholder } from "./-workspacePlaceholders";

export const Route = createFileRoute("/seeds/new")({
  component: NewSeedLotRoute,
});

function NewSeedLotRoute() {
  return (
    <WorkspacePlaceholder
      kicker="Seeds"
      title="New Seed Lot"
      actions={[
        { label: "Seeds", link: <WorkspaceLink to="/seeds">Seeds</WorkspaceLink> },
      ]}
    />
  );
}
