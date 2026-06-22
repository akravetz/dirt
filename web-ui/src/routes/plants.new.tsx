import { createFileRoute } from "@tanstack/react-router";
import { WorkspaceLink, WorkspacePlaceholder } from "./-workspacePlaceholders";

export const Route = createFileRoute("/plants/new")({
  component: NewPlantRoute,
});

function NewPlantRoute() {
  return (
    <WorkspacePlaceholder
      kicker="Plants"
      title="New Plant"
      actions={[
        { label: "Plants", link: <WorkspaceLink to="/plants">Plants</WorkspaceLink> },
      ]}
    />
  );
}
