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
 * How far along a step is, in whole percent, or `null` when its total isn't known.
 */
export function percentDone(
  done: number | null | undefined,
  total: number | null | undefined,
): number | null {
  if (done === null || done === undefined || total === null || total === undefined) {
    return null;
  }
  if (total === 0) {
    return 100;
  }
  return Math.round((done / total) * 100);
}

/**
 * A byte step's text, such as `Downloading: 340.0 MB of 1.2 GB`.
 */
function bytesText(name: string, done: number | null, total: number | null): string {
  if (done === null) {
    return name;
  }
  if (total === null) {
    return `${name}: ${formatBytes(done)}`;
  }
  return `${name}: ${formatBytes(done)} of ${formatBytes(total)}`;
}

/**
 * What a load or a link check is doing, by its stage, such as
 * `Unzipping: 340.0 MB of 1.2 GB` or `Copying data: 40%`, or `null` for no stage.
 *
 * Downloading and unzipping count bytes, copying counts percent, and swapping and
 * reading have no count.
 */
export function stageText(
  stage: string | null | undefined,
  done: number | null | undefined,
  total: number | null | undefined,
): string | null {
  const counted = done ?? null;
  const of = total ?? null;
  switch (stage) {
    case "downloading":
      return bytesText("Downloading", counted, of);
    case "unzipping":
      return bytesText("Unzipping", counted, of);
    case "copying":
      return counted === null ? "Copying data" : `Copying data: ${counted}%`;
    case "swapping":
      return "Swapping data";
    case "reading":
      return "Reading fields";
    default:
      return null;
  }
}
