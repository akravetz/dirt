import { createFileRoute } from "@tanstack/react-router";
import { Suspense } from "react";
import { NewPlantPage, StatusScreen } from "@/features/plants/PlantsWorkspace";

export const Route = createFileRoute("/plants/new")({
  component: NewPlantRoute,
  errorComponent: () => (
    <StatusScreen message="Failed to load plant creation." tone="danger" />
  ),
});

function NewPlantRoute() {
  return (
    <Suspense fallback={<StatusScreen message="Loading plant creation..." />}>
      <NewPlantPage />
    </Suspense>
  );
}
