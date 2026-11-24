import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vite-plus/test";

import { renderRoute } from "@/test/render";

const UNKNOWN_URL = "/this-page-does-not-exist";

describe("a URL with no page", () => {
  it("shows 404", async () => {
    renderRoute(UNKNOWN_URL);

    expect(await screen.findByRole("heading", { name: "404" })).toBeInTheDocument();
  });

  it("asks if the user is lost", async () => {
    renderRoute(UNKNOWN_URL);

    expect(await screen.findByRole("heading", { name: "Are you lost ?" })).toBeInTheDocument();
    expect(
      screen.getByText("try to reload this page or go back to the homepage"),
    ).toBeInTheDocument();
  });

  it("links to the homepage", async () => {
    renderRoute(UNKNOWN_URL);

    expect(await screen.findByRole("link", { name: "homepage" })).toHaveAttribute("href", "/");
  });

  it("goes to the homepage when the link is clicked", async () => {
    const user = userEvent.setup();
    renderRoute(UNKNOWN_URL);

    await user.click(await screen.findByRole("link", { name: "homepage" }));

    expect(await screen.findByRole("heading", { name: "Atlas" })).toBeInTheDocument();
  });
});
