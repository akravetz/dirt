import { createFileRoute } from "@tanstack/react-router";
import { Suspense } from "react";
import { NewPlantPage, StatusScreen } from "@/features/plants/PlantsWorkspace";
import { useSeedLotListQuery } from "@/features/seeds/seedsQueries";

export const Route = createFileRoute("/plants/new")({
  component: NewPlantRoute,
  errorComponent: () => (
    <StatusScreen message="Failed to load plant creation." tone="danger" />
  ),
});

function NewPlantRoute() {
  return (
    <Suspense fallback={<StatusScreen message="Loading plant creation..." />}>
      <NewPlantRouteContent />
    </Suspense>
  );
}

function NewPlantRouteContent() {
  const seedLots = useSeedLotListQuery();
  return <NewPlantPage seedLots={seedLots.seedLots} />;
}
