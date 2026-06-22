import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Suspense } from "react";
import { SeedLotDetailPage, SeedStatusScreen } from "@/features/seeds/SeedsWorkspace";
import { useIsLeafRoute } from "./-workspacePlaceholders";

export const Route = createFileRoute("/seeds/$seedLotId")({
  component: SeedLotRoute,
  errorComponent: () => (
    <SeedStatusScreen message="Failed to load seed-lot detail." tone="danger" />
  ),
});

function SeedLotRoute() {
  const { seedLotId } = Route.useParams();
  const isLeafRoute = useIsLeafRoute(Route.id);

  if (!isLeafRoute) return <Outlet />;

  return (
    <Suspense fallback={<SeedStatusScreen message="Loading seed-lot detail..." />}>
      <SeedLotDetailPage seedLotId={seedLotId} />
    </Suspense>
  );
}
