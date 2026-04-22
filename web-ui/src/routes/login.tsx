// Pre-auth /login route.
//
// Owns the POST /api/auth/login call on behalf of LoginScreen (the
// ui/ layer is forbidden to import api-client by boundaries/TS-05).
// On 200 → navigate to "/"; on 401 → surface the contract's ErrorDetail
// string back to the presentational component, which flips aria-invalid
// and renders the role="alert" block.
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { createDirtApiClient } from "@/api-client";
import { LoginScreen } from "@/ui/LoginScreen";

export const Route = createFileRoute("/login")({
  component: LoginPage,
});

// The shared api-client factory installs a 401 → /login redirect
// middleware by default; we're already here and want the 401 to bubble
// through as "invalid credentials", so disarm the redirect for this
// screen's client.
const api = createDirtApiClient({
  onUnauthorized: () => {},
});

function LoginPage() {
  const navigate = useNavigate();

  const onSubmit = async ({
    username,
    password,
  }: {
    username: string;
    password: string;
  }): Promise<string | null> => {
    const { data, error } = await api.POST("/api/auth/login", {
      body: { username, password },
    });
    if (data) {
      await navigate({ to: "/" });
      return null;
    }
    const detail =
      error && typeof error === "object" && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "invalid credentials";
    return detail === "invalid_credentials" ? "invalid credentials" : detail;
  };

  return <LoginScreen onSubmit={onSubmit} />;
}
