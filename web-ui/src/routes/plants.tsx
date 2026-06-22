import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Suspense } from "react";
import {
  BreedingLogbookPage,
  StatusScreen,
} from "@/features/breeding-logbook/BreedingLogbookPage";
import { useIsLeafRoute } from "./-workspacePlaceholders";

export const Route = createFileRoute("/plants")({
  component: PlantsRoute,
  errorComponent: () => <StatusScreen message="Failed to load plants." tone="danger" />,
});

function PlantsRoute() {
  const isLeafRoute = useIsLeafRoute(Route.id);

  if (!isLeafRoute) return <Outlet />;

  return (
    <Suspense fallback={<StatusScreen message="Loading plants..." />}>
      <BreedingLogbookPage />
    </Suspense>
  );
}
