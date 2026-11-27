import { useSyncExternalStore } from "react";

/**
 * How dates are shown, picked in the Dates menu.
 *
 * `timeZone` is `local` for the browser's own time zone, or a time zone name such as
 * `UTC` or `America/Chicago`. `style` is `relative` ("3 days ago", then the full date
 * once a time is 7 days old) or `full` (always the full date).
 */
export interface DateSettings {
  timeZone: string;
  style: "relative" | "full";
}

export const DEFAULT_DATE_SETTINGS: DateSettings = { timeZone: "local", style: "relative" };

// The localStorage key the settings are saved under, in this browser only.
const STORAGE_KEY = "atlas.dates";

const listeners = new Set<() => void>();
let cached: { raw: string | null; settings: DateSettings } | undefined;

function readRaw(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/**
 * Turn the saved text back into settings. Anything missing or damaged uses the default.
 */
function parse(raw: string | null): DateSettings {
  if (raw === null) return DEFAULT_DATE_SETTINGS;
  try {
    const saved: unknown = JSON.parse(raw);
    if (typeof saved !== "object" || saved === null) return DEFAULT_DATE_SETTINGS;
    const { timeZone, style } = saved as Partial<Record<keyof DateSettings, unknown>>;
    return {
      timeZone: typeof timeZone === "string" ? timeZone : DEFAULT_DATE_SETTINGS.timeZone,
      style: style === "relative" || style === "full" ? style : DEFAULT_DATE_SETTINGS.style,
    };
  } catch {
    return DEFAULT_DATE_SETTINGS;
  }
}

function getSnapshot(): DateSettings {
  const raw = readRaw();
  if (cached === undefined || cached.raw !== raw) cached = { raw, settings: parse(raw) };
  return cached.settings;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Save the date settings in this browser and update every date on the page.
 */
export function saveDateSettings(settings: DateSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Storage can be off, such as in a private window; the setting then lasts until reload.
    cached = { raw: readRaw(), settings };
  }
  for (const listener of listeners) listener();
}

/**
 * The current date settings. Components using this redraw when the settings change.
 */
export function useDateSettings(): DateSettings {
  return useSyncExternalStore(subscribe, getSnapshot);
}
