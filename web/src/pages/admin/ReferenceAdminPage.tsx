import {
  Alert,
  Anchor,
  Button,
  Checkbox,
  Group,
  List,
  MultiSelect,
  Progress,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { ApiError } from "@/api/fetcher";
import type { LayerRead, LoadRead, LoadRequest } from "@/api/generated";
import {
  getReferenceListLoadsQueryKey,
  useReferenceListLayers,
  useReferenceListLoads,
  useReferenceListStates,
  useReferenceStartLoads,
} from "@/api/generated";
import { DateSettingsMenu } from "@/dates/DateSettingsMenu";
import { useDateSettings } from "@/dates/dateSettings";
import { formatDate } from "@/dates/formatDate";

import classes from "./ReferenceAdminPage.module.css";
import { percentDone, stageText } from "./progressText";

/** How often the page asks for load status while a load is waiting or running. */
const LOAD_STATUS_INTERVAL_MS = 3000;

/** How long results stay on the page after the last load finishes. */
const RESULT_DISPLAY_MS = 5000;

/** The States option, and the table row, for every state at once. */
const ALL_STATES = "ALL";

/**
 * What one box shows: `waiting` for a requested load that hasn't started, the load
 * itself while it runs or once it has finished, or nothing.
 */
type BoxState = LoadRead | "waiting" | undefined;

/**
 * Key for one box in the load table.
 */
function boxKey(layer: string, state: string): string {
  return `${layer}|${state}`;
}

/**
 * Group layers by their readable group name, such as `Water`.
 *
 * Args:
 *   layers: The layers, in name order.
 *
 * Returns:
 *   Each group with its layers, in the order the groups first appear.
 */
function groupLayers(layers: LayerRead[]): [string, LayerRead[]][] {
  const groups = new Map<string, LayerRead[]>();
  for (const layer of layers) {
    groups.set(layer.group, [...(groups.get(layer.group) ?? []), layer]);
  }
  return [...groups];
}

/**
 * Turn a failed load request into the messages to show.
 *
 * The load endpoint answers 422 with a list of every problem. Any other failure shows
 * the request's own message.
 */
function errorMessages(error: unknown): string[] {
  if (error instanceof ApiError) {
    const body: unknown = error.body;
    if (typeof body === "object" && body !== null && "detail" in body) {
      const { detail } = body;
      if (Array.isArray(detail) && detail.every((item) => typeof item === "string")) {
        return detail;
      }
    }
  }
  return [error instanceof Error ? error.message : String(error)];
}

/**
 * When a box was last loaded, for a box with nothing running: `Updated 3 days ago`,
 * `Failed 2026-11-12 09:14` when its newest load failed, or `Never loaded`.
 */
function LastUpdated({ load }: { load: LoadRead | undefined }) {
  const dateSettings = useDateSettings();
  if (load === undefined || load.finished_at === null) {
    return <Text size="xs">Never loaded</Text>;
  }
  const when = formatDate(load.finished_at, dateSettings);
  return <Text size="xs">{`${load.status === "failed" ? "Failed" : "Updated"} ${when}`}</Text>;
}

interface LoadStatusProps {
  load: BoxState;
  label: string;
}

/**
 * One box's load: waiting, a bar and what it's doing while running, then the result.
 *
 * While downloading, unzipping, or copying, the bar fills as the stage goes, such as
 * `Unzipping: 340.0 MB of 1.2 GB`. When the stage has no count, it stays full and moving.
 */
function LoadStatus({ load, label }: LoadStatusProps) {
  if (load === undefined) return null;

  if (load === "waiting") {
    return (
      <Text size="sm" c="var(--color-med-dk-gray)">
        waiting
      </Text>
    );
  }

  if (load.status === "running") {
    const percent = percentDone(load.progress_done, load.progress_total);
    const text = stageText(load.stage, load.progress_done, load.progress_total);
    return (
      <Stack gap={4}>
        <Progress value={percent ?? 100} striped animated aria-label={`${label} running`} />
        {text !== null && <Text size="xs">{text}</Text>}
      </Stack>
    );
  }

  if (load.status === "succeeded") {
    return (
      <Stack gap={0}>
        <Text size="sm" c="var(--color-dk-green)">
          succeeded
        </Text>
        {load.rows_loaded !== null && (
          <Text size="xs">{`${load.rows_loaded.toLocaleString("en-US")} rows`}</Text>
        )}
      </Stack>
    );
  }

  return (
    <Stack gap={0}>
      <Text size="sm" c="var(--color-rust)">
        failed
      </Text>
      {load.error !== null && <Text size="xs">{load.error}</Text>}
    </Stack>
  );
}

interface AllStatesStatusProps {
  boxes: [string, BoxState][];
  label: string;
}

/**
 * The All states box: how many states are done while loads run, then a summary with
 * each failed state's error.
 *
 * Args:
 *   boxes: Each state's code and what its own box would show.
 *   label: The box's label, for the progress bar.
 */
function AllStatesStatus({ boxes, label }: AllStatesStatusProps) {
  const shown = boxes.filter(([, box]) => box !== undefined);
  if (shown.length === 0) return null;

  const done = shown.filter(([, box]) => box !== "waiting" && box?.status !== "running");
  if (done.length < shown.length) {
    return (
      <Stack gap={4}>
        <Progress
          value={(done.length / shown.length) * 100}
          striped
          animated
          aria-label={`${label} running`}
        />
        <Text size="xs">{`${done.length} of ${shown.length} states done`}</Text>
      </Stack>
    );
  }

  const failed = done.flatMap(([state, box]) =>
    box !== undefined && box !== "waiting" && box.status === "failed" ? [{ state, box }] : [],
  );
  if (failed.length === 0) {
    return (
      <Stack gap={0}>
        <Text size="sm" c="var(--color-dk-green)">
          succeeded
        </Text>
        <Text size="xs">{`${done.length} states`}</Text>
      </Stack>
    );
  }

  return (
    <Stack gap={0}>
      <Text size="sm" c="var(--color-rust)">
        {`${done.length - failed.length} succeeded, ${failed.length} failed`}
      </Text>
      {failed.map(({ state, box }) => (
        <Text key={state} size="xs">{`${state}: ${box.error ?? "no error recorded"}`}</Text>
      ))}
    </Stack>
  );
}

/**
 * Admin page for the reference database.
 *
 * Each layer group, such as Water, has its own table, with one row per picked state and
 * one column per layer. The tables show once a state is picked. Each box can be
 * checked, and one Load button sends every checked box as one load request.
 *
 * Picking All states shows one All states row; a box checked there loads that layer
 * for every state.
 *
 * The page shows only loads that are running or that were requested from it. Results
 * stay until 5 seconds after the last load finishes, then the page clears, the same as
 * a reload.
 */
export function ReferenceAdminPage() {
  const queryClient = useQueryClient();
  const [pickedStates, setPickedStates] = useState<string[]>([]);
  const [stateSearch, setStateSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Boxes to follow: each box's last load start time when it was requested, so the
  // page can tell the new load from the old one. null when it had no load before.
  const [followed, setFollowed] = useState<Map<string, string | null>>(new Map());

  const states = useReferenceListStates();
  const layers = useReferenceListLayers();
  const loads = useReferenceListLoads();

  const allStates = states.data?.data ?? [];
  const allLayers = layers.data?.data ?? [];
  const allLoads = loads.data?.data ?? [];

  const loadsByBox = new Map(allLoads.map((load) => [boxKey(load.layer, load.state), load]));
  const runningKeys = allLoads
    .filter((load) => load.status === "running")
    .map((load) => boxKey(load.layer, load.state));

  /**
   * What a box shows. A running load always shows; a finished one only when the box
   * is followed and the load is newer than the one before the request.
   */
  function boxState(key: string): BoxState {
    const load = loadsByBox.get(key);
    if (!followed.has(key)) return load?.status === "running" ? load : undefined;
    if (load === undefined || load.started_at === followed.get(key)) return "waiting";
    return load;
  }

  const followedKeys = [...followed.keys()];
  const active = runningKeys.length > 0 || followedKeys.some((key) => boxState(key) === "waiting");

  const startLoads = useReferenceStartLoads({
    mutation: {
      onSuccess: async (_response, { data }) => {
        const next = new Map(followed);
        for (const { layer, state } of data) {
          const key = boxKey(layer, state);
          next.set(key, loadsByBox.get(key)?.started_at ?? null);
        }
        setFollowed(next);
        setSelected(new Set());
        await queryClient.invalidateQueries({ queryKey: getReferenceListLoadsQueryKey() });
      },
    },
  });

  // Follow loads found running, such as after a reload, so their result shows too.
  // Set during render (React's pattern for adjusting state when data changes); it runs
  // again only until every running load is followed.
  const unfollowed = runningKeys.filter((key) => !followed.has(key));
  if (unfollowed.length > 0) {
    setFollowed(new Map([...followed, ...unfollowed.map((key) => [key, null] as const)]));
  }

  // Ask for load status every few seconds while anything is waiting or running.
  useEffect(() => {
    if (!active) return undefined;
    const timer = setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: getReferenceListLoadsQueryKey() });
    }, LOAD_STATUS_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [active, queryClient]);

  // Clear the page a short time after the last followed load finishes.
  useEffect(() => {
    if (active || followed.size === 0) return undefined;
    const timer = setTimeout(() => {
      setFollowed(new Map());
      setPickedStates([]);
      setSelected(new Set());
    }, RESULT_DISPLAY_MS);
    return () => clearTimeout(timer);
  }, [active, followed]);

  const allStatesPicked = pickedStates.includes(ALL_STATES);
  const rows = allStatesPicked
    ? [ALL_STATES]
    : [
        ...new Set([
          ...pickedStates,
          ...followedKeys.map((key) => key.split("|")[1]),
          ...runningKeys.map((key) => key.split("|")[1]),
        ]),
      ].sort();

  const stateOptions = [
    { value: ALL_STATES, label: "All states" },
    ...allStates.map((state) => ({ value: state.code, label: `${state.name} (${state.code})` })),
  ];

  /**
   * Change the picked states. All states replaces any picked states, and a state picked
   * after All states replaces it. Checked boxes of states no longer shown are dropped.
   */
  function pickStates(values: string[]) {
    const added = values.filter((value) => !pickedStates.includes(value));
    let next = values;
    if (added.includes(ALL_STATES)) {
      next = [ALL_STATES];
    } else if (added.length > 0) {
      next = values.filter((value) => value !== ALL_STATES);
    }
    setPickedStates(next);
    setSelected(new Set([...selected].filter((key) => next.includes(key.split("|")[1]))));
    setStateSearch("");
  }

  function toggle(key: string) {
    const next = new Set(selected);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setSelected(next);
  }

  /**
   * Check every box in `keys`, or uncheck them all when they're all checked already.
   */
  function toggleAll(keys: string[]) {
    const next = new Set(selected);
    if (keys.every((key) => next.has(key))) {
      for (const key of keys) next.delete(key);
    } else {
      for (const key of keys) next.add(key);
    }
    setSelected(next);
  }

  /**
   * Checked state of a heading checkbox for the boxes in `keys`.
   */
  function headingCheck(keys: string[]) {
    const count = keys.filter((key) => selected.has(key)).length;
    return {
      checked: keys.length > 0 && count === keys.length,
      indeterminate: count > 0 && count < keys.length,
      disabled: keys.length === 0,
    };
  }

  const everyKey = allLayers.flatMap((layer) => rows.map((state) => boxKey(layer.name, state)));

  function sendLoads() {
    const data: LoadRequest[] = [];
    for (const state of rows) {
      const codes = state === ALL_STATES ? allStates.map((item) => item.code) : [state];
      for (const layer of allLayers) {
        if (selected.has(boxKey(layer.name, state))) {
          data.push(...codes.map((code) => ({ layer: layer.name, state: code })));
        }
      }
    }
    startLoads.mutate({ data });
  }

  function rowName(state: string): string {
    return state === ALL_STATES ? "All states" : state;
  }

  return (
    <>
      <header className={classes.header}>
        <Title order={1}>Reference database</Title>
      </header>

      <main className={classes.content}>
        <section className={classes.section}>
          <Group justify="space-between" align="start">
            <Title order={2} className={classes.accent}>
              Load
            </Title>
            <Group>
              <Anchor component={Link} to="/admin/reference/sources">
                Sources
              </Anchor>
              <DateSettingsMenu />
            </Group>
          </Group>

          <Group align="end">
            <MultiSelect
              label="States"
              placeholder="State name or code, or All states"
              data={stateOptions}
              value={pickedStates}
              onChange={pickStates}
              searchable
              searchValue={stateSearch}
              onSearchChange={setStateSearch}
              hidePickedOptions
              flex={1}
            />
            <Button
              variant="default"
              onClick={() => pickStates([])}
              disabled={pickedStates.length === 0}
            >
              Clear states
            </Button>
          </Group>

          {startLoads.isError && (
            <Alert color="var(--color-rust)" title="The loads didn't start">
              <List>
                {errorMessages(startLoads.error).map((message) => (
                  <List.Item key={message}>{message}</List.Item>
                ))}
              </List>
            </Alert>
          )}
        </section>

        {rows.length > 0 &&
          groupLayers(allLayers).map(([group, layersInGroup]) => (
            <section key={group} className={classes.group}>
              <Title order={3}>{group}</Title>
              <Table.ScrollContainer minWidth={0} type="native">
                <Table
                  withTableBorder
                  withColumnBorders
                  className={classes.table}
                  aria-label={group}
                >
                  <colgroup>
                    <col className={classes.stateColumn} />
                    {layersInGroup.map((layer) => (
                      <col key={layer.name} className={classes.layerColumn} />
                    ))}
                  </colgroup>
                  <Table.Thead>
                    <Table.Tr className={classes.headRow}>
                      <Table.Th>State</Table.Th>
                      {layersInGroup.map((layer) => {
                        const keys = rows.map((state) => boxKey(layer.name, state));
                        return (
                          <Table.Th key={layer.name}>
                            <Checkbox
                              label={layer.title}
                              title={`Check ${layer.title} for every state`}
                              {...headingCheck(keys)}
                              onChange={() => toggleAll(keys)}
                            />
                          </Table.Th>
                        );
                      })}
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {rows.map((state) => {
                      const keys = layersInGroup.map((layer) => boxKey(layer.name, state));
                      return (
                        <Table.Tr key={state}>
                          <Table.Th scope="row">
                            <Checkbox
                              label={rowName(state)}
                              title={`Check every ${group} layer for ${rowName(state)}`}
                              {...headingCheck(keys)}
                              onChange={() => toggleAll(keys)}
                            />
                          </Table.Th>
                          {layersInGroup.map((layer) => {
                            const key = boxKey(layer.name, state);
                            const label = `Load ${layer.title} for ${rowName(state)}`;
                            return (
                              <Table.Td key={key}>
                                <Stack gap="xs">
                                  <Checkbox
                                    aria-label={label}
                                    checked={selected.has(key)}
                                    onChange={() => toggle(key)}
                                  />
                                  {state === ALL_STATES ? (
                                    <AllStatesStatus
                                      boxes={allStates.map(({ code }) => [
                                        code,
                                        boxState(boxKey(layer.name, code)),
                                      ])}
                                      label={label}
                                    />
                                  ) : boxState(key) === undefined ? (
                                    <LastUpdated load={loadsByBox.get(key)} />
                                  ) : (
                                    <LoadStatus load={boxState(key)} label={label} />
                                  )}
                                </Stack>
                              </Table.Td>
                            );
                          })}
                        </Table.Tr>
                      );
                    })}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </section>
          ))}
      </main>

      {rows.length > 0 && (
        <footer className={classes.actions}>
          <Text className={classes.selectedCount}>{`${selected.size} loads selected`}</Text>
          <Button
            variant="default"
            onClick={() => setSelected(new Set(everyKey))}
            disabled={everyKey.length === 0}
          >
            Select all
          </Button>
          <Button
            variant="default"
            onClick={() => setSelected(new Set())}
            disabled={selected.size === 0}
          >
            Clear
          </Button>
          <Button onClick={sendLoads} disabled={selected.size === 0} loading={startLoads.isPending}>
            Load
          </Button>
        </footer>
      )}
    </>
  );
}
