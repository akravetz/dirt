import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Suspense } from "react";
import { PlantDetailPage, StatusScreen } from "@/features/plants/PlantsWorkspace";
import { useIsLeafRoute } from "./-workspacePlaceholders";

export const Route = createFileRoute("/plants/$plantKey")({
  component: PlantRoute,
  errorComponent: () => (
    <StatusScreen message="Failed to load plant detail." tone="danger" />
  ),
});

function PlantRoute() {
  const { plantKey } = Route.useParams();
  const isLeafRoute = useIsLeafRoute(Route.id);

  if (!isLeafRoute) return <Outlet />;

  return (
    <Suspense fallback={<StatusScreen message="Loading plant detail..." />}>
      <PlantDetailPage plantKey={plantKey} />
    </Suspense>
  );
}
