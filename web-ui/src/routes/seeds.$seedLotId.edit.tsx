import { createFileRoute } from "@tanstack/react-router";
import { WorkspaceLink, WorkspacePlaceholder } from "./-workspacePlaceholders";

export const Route = createFileRoute("/seeds/$seedLotId/edit")({
  component: EditSeedLotRoute,
});

function EditSeedLotRoute() {
  const { seedLotId } = Route.useParams();

  return (
    <WorkspacePlaceholder
      kicker="Edit seed lot"
      title={seedLotId}
      facts={[{ label: "Seed lot", value: seedLotId }]}
      actions={[
        { label: "Seeds", link: <WorkspaceLink to="/seeds">Seeds</WorkspaceLink> },
      ]}
    />
  );
}
