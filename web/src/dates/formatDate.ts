import { tz } from "@date-fns/tz";
import { differenceInMilliseconds, format, formatDistance } from "date-fns";

import type { DateSettings } from "@/dates/dateSettings";

// In relative style, times this old or older show the full date instead.
const RELATIVE_LIMIT_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * Show a time from the API the way the Dates menu says.
 *
 * Relative style gives "5 minutes ago" or "3 days ago" until the time is 7 days old,
 * then the full date. The full date is ISO style with a 24-hour clock, such as
 * `2026-11-26 14:48`, in the picked time zone. UTC times end in `Z`, such as
 * `2026-11-26 19:48Z`.
 *
 * Args:
 *   value: A time from the API, such as `2026-11-26T19:48:00Z`.
 *   settings: The time zone and style picked in the Dates menu.
 *   now: The current time, so a page shows every date against the same moment.
 */
export function formatDate(value: string, settings: DateSettings, now: Date = new Date()): string {
  const date = new Date(value);
  if (settings.style === "relative" && differenceInMilliseconds(now, date) < RELATIVE_LIMIT_MS) {
    return formatDistance(date, now, { addSuffix: true });
  }
  if (settings.timeZone === "local") return format(date, "yyyy-MM-dd HH:mm");
  const text = format(date, "yyyy-MM-dd HH:mm", { in: tz(settings.timeZone) });
  return settings.timeZone === "UTC" ? `${text}Z` : text;
}
