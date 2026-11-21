import { screen } from "@testing-library/react";
import { describe, expect, it } from "vite-plus/test";

import { HomePage } from "@/pages/HomePage";
import { render } from "@/test/render";

describe("HomePage", () => {
  it("shows the Atlas heading", () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "Atlas" })).toBeInTheDocument();
  });
});
