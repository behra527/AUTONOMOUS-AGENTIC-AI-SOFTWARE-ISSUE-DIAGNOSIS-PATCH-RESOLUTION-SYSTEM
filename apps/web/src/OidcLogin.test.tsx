import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UserManager } from "oidc-client-ts";
import OidcLogin from "./OidcLogin";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it("does not allow SSO when provider configuration is missing", () => {
  render(<OidcLogin onToken={async () => {}} />);
  expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
});
it("starts authorization-code redirect through the configured OIDC manager", async () => {
  const redirect = vi
    .spyOn(UserManager.prototype, "signinRedirect")
    .mockResolvedValue();
  render(
    <OidcLogin
      config={{
        authority: "https://identity.example",
        client_id: "web",
        redirect_uri: "http://localhost/",
        scope: "openid profile",
      }}
      onToken={async () => {}}
    />,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Sign in with your organization" }),
  );
  expect(redirect).toHaveBeenCalledOnce();
});
