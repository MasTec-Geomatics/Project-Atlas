import { Button, Popover, Radio, Select, Stack } from "@mantine/core";

import { saveDateSettings, useDateSettings } from "@/dates/dateSettings";

// Every time zone the browser knows, with Local and UTC first.
const TIME_ZONES = [
  { value: "local", label: "Local" },
  { value: "UTC", label: "UTC" },
  ...Intl.supportedValuesOf("timeZone")
    .filter((name) => name !== "UTC")
    .map((name) => ({ value: name, label: name })),
];

/**
 * The Dates menu: the time zone and style every date on the page is shown in.
 *
 * The choice is saved in this browser, so it stays the same on every page and visit.
 */
export function DateSettingsMenu() {
  const settings = useDateSettings();

  return (
    <Popover position="bottom-end" withinPortal>
      <Popover.Target>
        <Button variant="default">Dates</Button>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack>
          <Select
            label="Time zone"
            data={TIME_ZONES}
            value={settings.timeZone}
            onChange={(timeZone) => {
              if (timeZone !== null) saveDateSettings({ ...settings, timeZone });
            }}
            searchable
            allowDeselect={false}
            comboboxProps={{ withinPortal: false }}
          />
          <Radio.Group
            label="Style"
            value={settings.style}
            onChange={(style) =>
              saveDateSettings({ ...settings, style: style === "full" ? "full" : "relative" })
            }
          >
            <Stack gap="xs">
              <Radio value="relative" label="Relative" />
              <Radio value="full" label="Full date" />
            </Stack>
          </Radio.Group>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}
