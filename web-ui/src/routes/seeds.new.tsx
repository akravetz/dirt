import { createFileRoute } from "@tanstack/react-router";
import { Suspense } from "react";
import { NewSeedLotPage, SeedStatusScreen } from "@/features/seeds/SeedsWorkspace";

export const Route = createFileRoute("/seeds/new")({
  component: NewSeedLotRoute,
  errorComponent: () => (
    <SeedStatusScreen message="Failed to load seed-lot creation." tone="danger" />
  ),
});

function NewSeedLotRoute() {
  return (
    <Suspense fallback={<SeedStatusScreen message="Loading seed-lot creation..." />}>
      <NewSeedLotPage />
    </Suspense>
  );
}
