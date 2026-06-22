import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Suspense } from "react";
import {
  normalizeSeedsSearch,
  SeedStatusScreen,
  SeedsListPage,
  validateSeedsSearch,
} from "@/features/seeds/SeedsWorkspace";
import { useIsLeafRoute } from "./-workspacePlaceholders";

export const Route = createFileRoute("/seeds")({
  validateSearch: validateSeedsSearch,
  component: SeedsRoute,
  errorComponent: () => (
    <SeedStatusScreen message="Failed to load seeds." tone="danger" />
  ),
});

function SeedsRoute() {
  const isLeafRoute = useIsLeafRoute(Route.id);
  const search = normalizeSeedsSearch(Route.useSearch());

  if (!isLeafRoute) return <Outlet />;

  return (
    <Suspense fallback={<SeedStatusScreen message="Loading seeds..." />}>
      <SeedsListPage search={search} />
    </Suspense>
  );
}
