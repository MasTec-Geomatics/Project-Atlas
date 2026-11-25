import {
  Alert,
  Button,
  Checkbox,
  Group,
  List,
  Progress,
  Select,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "@/api/fetcher";
import type { LoadRead, LoadRequest } from "@/api/generated";
import {
  getReferenceListLoadsQueryKey,
  useReferenceListLayers,
  useReferenceListLoads,
  useReferenceListStates,
  useReferenceStartLoads,
} from "@/api/generated";

/**
 * How often the page asks for load status while a load is running.
 */
const LOAD_STATUS_INTERVAL_MS = 3000;

/**
 * Key for one box in the load table.
 */
function boxKey(layer: string, state: string): string {
  return `${layer}|${state}`;
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

interface LoadStatusProps {
  load: LoadRead | undefined;
  label: string;
}

/**
 * The last load of one layer and state: a moving bar while running, then the result.
 */
function LoadStatus({ load, label }: LoadStatusProps) {
  if (load === undefined) return null;

  if (load.status === "running") {
    return <Progress value={100} striped animated aria-label={`${label} running`} />;
  }

  if (load.status === "succeeded") {
    return (
      <Stack gap={0}>
        <Text size="sm" c="green">
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
      <Text size="sm" c="red">
        failed
      </Text>
      {load.error !== null && <Text size="xs">{load.error}</Text>}
    </Stack>
  );
}

/**
 * Admin page for the reference database.
 *
 * The load table has one row per state and one column per layer. Each box can be
 * checked, and one Load button sends every checked box as one load request.
 */
export function ReferenceAdminPage() {
  const queryClient = useQueryClient();
  const [addedStates, setAddedStates] = useState<string[]>([]);
  const [stateSearch, setStateSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const states = useReferenceListStates();
  const layers = useReferenceListLayers();
  const loads = useReferenceListLoads({
    query: {
      refetchInterval: (query) =>
        query.state.data?.data.some((load) => load.status === "running")
          ? LOAD_STATUS_INTERVAL_MS
          : false,
    },
  });
  const startLoads = useReferenceStartLoads({
    mutation: {
      onSuccess: async () => {
        setSelected(new Set());
        await queryClient.invalidateQueries({ queryKey: getReferenceListLoadsQueryKey() });
      },
    },
  });

  const allStates = states.data?.data ?? [];
  const allLayers = layers.data?.data ?? [];
  const allLoads = loads.data?.data ?? [];

  const loadsByBox = new Map(allLoads.map((load) => [boxKey(load.layer, load.state), load]));
  const rows = [...new Set([...allLoads.map((load) => load.state), ...addedStates])].sort();

  const stateOptions = allStates
    .filter((state) => !rows.includes(state.code))
    .map((state) => ({ value: state.code, label: `${state.name} (${state.code})` }));

  function addState(code: string | null) {
    if (code !== null && !addedStates.includes(code)) {
      setAddedStates([...addedStates, code]);
    }
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

  function sendLoads() {
    const data: LoadRequest[] = [];
    for (const state of rows) {
      for (const layer of allLayers) {
        if (selected.has(boxKey(layer, state))) data.push({ layer, state });
      }
    }
    startLoads.mutate({ data });
  }

  return (
    <Stack p="md">
      <Title order={1}>Reference database</Title>

      <Title order={2}>Load</Title>

      <Select
        label="Add a state"
        placeholder="State name or code"
        data={stateOptions}
        value={null}
        onChange={addState}
        searchable
        searchValue={stateSearch}
        onSearchChange={setStateSearch}
      />

      <Table withTableBorder withColumnBorders>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>State</Table.Th>
            {allLayers.map((layer) => (
              <Table.Th key={layer}>{layer}</Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((state) => (
            <Table.Tr key={state}>
              <Table.Th scope="row">{state}</Table.Th>
              {allLayers.map((layer) => {
                const key = boxKey(layer, state);
                const label = `Load ${layer} for ${state}`;
                return (
                  <Table.Td key={key}>
                    <Stack gap="xs">
                      <Checkbox
                        aria-label={label}
                        checked={selected.has(key)}
                        onChange={() => toggle(key)}
                      />
                      <LoadStatus load={loadsByBox.get(key)} label={label} />
                    </Stack>
                  </Table.Td>
                );
              })}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Group>
        <Text>{`${selected.size} loads selected`}</Text>
        <Button onClick={sendLoads} disabled={selected.size === 0} loading={startLoads.isPending}>
          Load
        </Button>
      </Group>

      {startLoads.isError && (
        <Alert color="red" title="The loads didn't start">
          <List>
            {errorMessages(startLoads.error).map((message) => (
              <List.Item key={message}>{message}</List.Item>
            ))}
          </List>
        </Alert>
      )}
    </Stack>
  );
}
