import {MantineProvider} from "@mantine/core";
import {render as testingLibraryRender} from "@testing-library/react";
import type {ReactNode} from "react";

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
