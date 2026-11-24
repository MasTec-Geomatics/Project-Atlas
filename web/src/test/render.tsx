import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { render as testingLibraryRender } from "@testing-library/react";
import type { ReactNode } from "react";

import { routeTree } from "@/routeTree.gen";

/**
 * Render a component inside MantineProvider, which every Mantine component needs.
 */
export function render(ui: ReactNode) {
  return testingLibraryRender(ui, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <MantineProvider env="test">{children}</MantineProvider>
    ),
  });
}

/**
 * Render the app at a URL, the way a user opens it in the browser.
 *
 * The test goes through the app's router, so it never imports the page it tests. A URL
 * with no page yet shows the router's "Not Found" message, and the test fails on what it
 * checks.
 *
 * Each render gets its own QueryClient, so no cached data carries over between tests.
 * Retries are off so a failed request shows its error right away.
 *
 * Args:
 *  path: The URL to open, such as `/admin/reference`.
 */
export function renderRoute(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });

  return testingLibraryRender(
    <QueryClientProvider client={queryClient}>
      <MantineProvider env="test">
        <RouterProvider router={router} />
      </MantineProvider>
    </QueryClientProvider>,
  );
}
