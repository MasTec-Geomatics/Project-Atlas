import "@testing-library/jest-dom/vitest";

import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vite-plus/test";

// How long findBy and waitFor wait. The default, 1 second, is too short for the first
// test in a file on a slower machine, which also loads the page and its libraries.
configure({ asyncUtilTimeout: 5000 });

// jsdom lacks these browser APIs, and Mantine components call them.
// This follows Mantine's "Testing with Vitest" guide.
const getComputedStyle = window.getComputedStyle.bind(window); // the bind method differs from
// Mantine's guide but fixes an Oxlint warning
window.getComputedStyle = (element) => getComputedStyle(element);
window.HTMLElement.prototype.scrollIntoView = () => {};
// The router scrolls to the top on each page change; jsdom has no scrolling.
window.scrollTo = () => {};

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

class ResizedObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

window.ResizeObserver = ResizedObserver;

afterEach(() => {
  cleanup();
  // Saved settings, such as the Dates menu's, must not carry over between tests.
  localStorage.clear();
});
