import { createFileRoute } from "@tanstack/react-router";
import { WorkspaceLink, WorkspacePlaceholder } from "./-workspacePlaceholders";

export const Route = createFileRoute("/plants/$plantKey/edit")({
  component: EditPlantRoute,
});

function EditPlantRoute() {
  const { plantKey } = Route.useParams();

  return (
    <WorkspacePlaceholder
      kicker="Edit plant"
      title={plantKey}
      facts={[{ label: "Plant key", value: plantKey }]}
      actions={[
        { label: "Plants", link: <WorkspaceLink to="/plants">Plants</WorkspaceLink> },
      ]}
    />
  );
}
