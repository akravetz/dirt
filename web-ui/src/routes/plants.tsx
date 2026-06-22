import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Suspense } from "react";
import {
  normalizePlantsSearch,
  PlantsListPage,
  StatusScreen,
  validatePlantsSearch,
} from "@/features/plants/PlantsWorkspace";
import { useIsLeafRoute } from "./-workspacePlaceholders";

export const Route = createFileRoute("/plants")({
  validateSearch: validatePlantsSearch,
  component: PlantsRoute,
  errorComponent: () => <StatusScreen message="Failed to load plants." tone="danger" />,
});

function PlantsRoute() {
  const isLeafRoute = useIsLeafRoute(Route.id);
  const search = normalizePlantsSearch(Route.useSearch());

  if (!isLeafRoute) return <Outlet />;

  return (
    <Suspense fallback={<StatusScreen message="Loading plants..." />}>
      <PlantsListPage search={search} />
    </Suspense>
  );
}
