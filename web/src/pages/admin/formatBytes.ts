const UNITS = ["bytes", "KB", "MB", "GB", "TB"];

/**
 * Format a byte count for people, such as `340.0 MB` or `1.2 GB`.
 *
 * Uses 1,024 bytes per KB, the way file managers and browsers show download sizes.
 */
export function formatBytes(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return unit === 0 ? `${value} bytes` : `${value.toFixed(1)} ${UNITS[unit]}`;
}

/**
 * How far along a download is, in whole percent, or `null` when its size isn't known.
 */
export function downloadPercent(done: number | null, total: number | null): number | null {
  if (done === null || total === null || total === 0) {
    return null;
  }
  return Math.round((done / total) * 100);
}

/**
 * What a download has done so far, such as `Downloading: 340.0 MB of 1.2 GB`.
 */
export function downloadText(done: number | null, total: number | null): string {
  if (done === null) {
    return "Downloading";
  }
  if (total === null) {
    return `Downloading: ${formatBytes(done)}`;
  }
  return `Downloading: ${formatBytes(done)} of ${formatBytes(total)}`;
}
