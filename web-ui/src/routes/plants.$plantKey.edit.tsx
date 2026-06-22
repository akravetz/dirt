import { createFileRoute } from "@tanstack/react-router";
import { Suspense } from "react";
import { PlantDetailPage, StatusScreen } from "@/features/plants/PlantsWorkspace";

export const Route = createFileRoute("/plants/$plantKey/edit")({
  component: EditPlantRoute,
  errorComponent: () => (
    <StatusScreen message="Failed to load plant editor." tone="danger" />
  ),
});

function EditPlantRoute() {
  const { plantKey } = Route.useParams();

  return (
    <Suspense fallback={<StatusScreen message="Loading plant editor..." />}>
      <PlantDetailPage editMode plantKey={plantKey} />
    </Suspense>
  );
}
