import { createFileRoute } from "@tanstack/react-router";
import { Suspense } from "react";
import { NewSeedLotPage, StatusScreen } from "@/features/plants/PlantsWorkspace";

export const Route = createFileRoute("/seeds/new")({
  component: NewSeedLotRoute,
  errorComponent: () => (
    <StatusScreen message="Failed to load seed-lot creation." tone="danger" />
  ),
});

function NewSeedLotRoute() {
  return (
    <Suspense fallback={<StatusScreen message="Loading seed-lot creation..." />}>
      <NewSeedLotPage />
    </Suspense>
  );
}
