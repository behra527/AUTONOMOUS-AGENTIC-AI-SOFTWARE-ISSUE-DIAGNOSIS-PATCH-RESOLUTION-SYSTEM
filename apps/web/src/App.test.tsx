import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/health")
          ? { auth_mode: "demo", model_mode: "demo" }
          : url.endsWith("/auth/me")
            ? {
                subject: "customer",
                memberships: [{ project_id: "p1", role: "customer" }],
              }
            : url.endsWith("/projects")
              ? [{ id: "p1", name: "Demo" }]
              : { items: [], next_cursor: null },
    })),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("customer can open the report form without internal repository controls", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
  await userEvent.click(
    await screen.findByRole("button", { name: /Enter as customer/i }),
  );
  await screen.findByText("Your reported issues");
  expect(screen.queryByRole("button", { name: "Repositories" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "New issue" }));
  expect(await screen.findByRole("dialog")).toBeTruthy();
  expect(screen.getByLabelText("Issue title")).toBeTruthy();
  client.clear();
});

it("keeps queued investigations visible while diagnosis is still empty", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () => {
        if (url.endsWith("/health"))
          return { auth_mode: "demo", model_mode: "demo" };
        if (url.endsWith("/auth/me"))
          return {
            subject: "engineer",
            memberships: [{ project_id: "p1", role: "engineer" }],
          };
        if (url.endsWith("/projects")) return [{ id: "p1", name: "Demo" }];
        if (url.endsWith("/tickets"))
          return {
            items: [
              {
                id: "t1",
                title: "PDF upload broken",
                description: "Example report",
                expected_behavior: "Accept",
                actual_behavior: "Crash",
                reproduction_steps: ["Upload"],
                status: "QUEUED",
                created_at: "2026-11-01T00:00:00Z",
              },
            ],
            next_cursor: null,
          };
        if (url.endsWith("/investigations"))
          return [
            {
              id: "r1",
              status: "QUEUED",
              diagnosis: {},
              created_at: "2026-11-01T00:00:00Z",
            },
          ];
        return [];
      },
    })),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
  await userEvent.click(
    await screen.findByRole("button", { name: /Enter as engineer/i }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: /PDF upload broken/i }),
  );
  expect(
    await screen.findByText(
      "Investigation in progress. This view updates automatically.",
    ),
  ).toBeTruthy();
  client.clear();
});
