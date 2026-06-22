import { createFileRoute } from "@tanstack/react-router";
import { Suspense } from "react";
import { SeedLotDetailPage, SeedStatusScreen } from "@/features/seeds/SeedsWorkspace";

export const Route = createFileRoute("/seeds/$seedLotId/edit")({
  component: EditSeedLotRoute,
  errorComponent: () => (
    <SeedStatusScreen message="Failed to load seed-lot editor." tone="danger" />
  ),
});

function EditSeedLotRoute() {
  const { seedLotId } = Route.useParams();

  return (
    <Suspense fallback={<SeedStatusScreen message="Loading seed-lot editor..." />}>
      <SeedLotDetailPage editMode seedLotId={seedLotId} />
    </Suspense>
  );
}
