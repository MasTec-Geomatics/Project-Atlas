import {
  Alert,
  Anchor,
  Button,
  Checkbox,
  Drawer,
  Group,
  Progress,
  Radio,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  VisuallyHidden,
} from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import { checkSource } from "@/api/checkSource";
import { ApiError } from "@/api/fetcher";
import type { CheckEvent, LayerRead, SourceRead, StateRead } from "@/api/generated";
import {
  getReferenceListSourceChecksQueryKey,
  getReferenceListSourcesQueryKey,
  useReferenceCreateSource,
  useReferenceListLayers,
  useReferenceListSourceChecks,
  useReferenceListSources,
  useReferenceListStates,
  useReferenceRunSourceChecks,
  useReferenceUpdateSource,
} from "@/api/generated";
import { DateSettingsMenu } from "@/dates/DateSettingsMenu";
import { useDateSettings } from "@/dates/dateSettings";
import { formatDate } from "@/dates/formatDate";

import { downloadPercent, downloadText } from "./formatBytes";
import classes from "./ReferenceSourcesPage.module.css";

/** The State option for a source that covers every state. */
const FEDERAL = "FEDERAL";

/**
 * The form's values. `columns` maps each of the layer's columns to the field picked for
 * it, or `null` when none is picked.
 */
interface FormValues {
  layer: string | null;
  state: string | null;
  checkState: string | null;
  downloadUrl: string;
  accessType: string;
  format: string | null;
  sourceLayer: string | null;
  datasetLayers: { name: string; fields: string[] }[];
  columns: Record<string, string | null>;
  clipToState: boolean;
  license: string;
  attribution: string;
  isEnabled: boolean;
}

const EMPTY_FORM: FormValues = {
  layer: null,
  state: null,
  checkState: null,
  downloadUrl: "",
  accessType: "file",
  format: null,
  sourceLayer: null,
  datasetLayers: [],
  columns: {},
  clipToState: false,
  license: "",
  attribution: "",
  isEnabled: true,
};

/**
 * The form's values for an existing source. Its current fields are the only choices
 * until the link is checked again.
 */
function formFromSource(source: SourceRead): FormValues {
  const fields = Object.values(source.field_mapping);
  return {
    ...EMPTY_FORM,
    layer: source.layer,
    state: source.state ?? FEDERAL,
    downloadUrl: source.download_url,
    accessType: source.access_type,
    format: source.format,
    sourceLayer: source.source_layer,
    datasetLayers: [{ name: source.source_layer ?? "", fields }],
    columns: source.field_mapping,
    clipToState: source.clip_to_state,
    license: source.license ?? "",
    attribution: source.attribution ?? "",
    isEnabled: source.is_enabled,
  };
}

/**
 * Turn a failed request into the message to show. FastAPI puts it in `detail`.
 */
function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const body: unknown = error.body;
    if (typeof body === "object" && body !== null && "detail" in body) {
      const { detail } = body;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) return detail.map(String).join("; ");
    }
  }
  return error instanceof Error ? error.message : String(error);
}

/**
 * What a running link check is doing: opening the link, downloading, or reading fields.
 */
function checkText(event: CheckEvent | null): string {
  if (event?.stage === "downloading") {
    return downloadText(event.bytes_downloaded ?? null, event.bytes_total ?? null);
  }
  if (event?.stage === "reading") {
    return "Reading fields";
  }
  return "Opening the link";
}

/**
 * The picked fields, leaving out columns with no field picked.
 */
function fieldMapping(columns: Record<string, string | null>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(columns).flatMap(([column, field]) => (field ? [[column, field]] : [])),
  );
}

/**
 * A source's name for people: its layer title and state, such as `Wetlands, Federal`.
 */
function sourceName(source: SourceRead, layers: LayerRead[]): string {
  const title = layers.find((layer) => layer.name === source.layer)?.title ?? source.layer;
  return `${title}, ${source.state ?? "Federal"}`;
}

/**
 * The Layer dropdown's options, grouped under their group name, such as `Water`.
 */
function layerOptions(layers: LayerRead[]) {
  const groups = new Map<string, { value: string; label: string }[]>();
  for (const layer of layers) {
    groups.set(layer.group, [
      ...(groups.get(layer.group) ?? []),
      { value: layer.name, label: layer.title },
    ]);
  }
  return [...groups].map(([group, items]) => ({ group, items }));
}

interface SourceFormProps {
  editing: SourceRead | null;
  layers: LayerRead[];
  states: StateRead[];
  onSaved: () => void;
}

/**
 * The Add source and Edit source form.
 *
 * Check link opens the link and fills in the format, the dataset layer, and the field
 * for each column it could match. While it runs, a bar shows the download's progress,
 * then reading the fields. The load uses the file Check link downloaded. Save stays off
 * until the link is checked, and again after the layer, state, link, or type changes.
 */
function SourceForm({ editing, layers, states, onSaved }: SourceFormProps) {
  const [form, setForm] = useState<FormValues>(editing ? formFromSource(editing) : EMPTY_FORM);

  // The running check's latest progress, whether a check is running, and why the last
  // one failed. Changing the link stops a running check.
  const [checkProgress, setCheckProgress] = useState<CheckEvent | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const checkAbort = useRef<AbortController | null>(null);
  useEffect(() => () => checkAbort.current?.abort(), []);

  const create = useReferenceCreateSource({ mutation: { onSuccess: onSaved } });
  const update = useReferenceUpdateSource({ mutation: { onSuccess: onSaved } });
  const save = editing ? update : create;

  const federal = form.state === FEDERAL;
  const stateToCheck = federal ? form.checkState : form.state;

  /**
   * Change fields that decide what the link holds. The last check no longer applies.
   */
  function changeLink(values: Partial<FormValues>) {
    checkAbort.current?.abort();
    setChecking(false);
    setCheckError(null);
    setForm({
      ...form,
      ...values,
      format: null,
      sourceLayer: null,
      datasetLayers: [],
      columns: {},
    });
  }

  async function runCheck() {
    if (form.layer === null || stateToCheck === null) return;
    const abort = new AbortController();
    checkAbort.current = abort;
    setChecking(true);
    setCheckProgress(null);
    setCheckError(null);
    try {
      await checkSource(
        {
          layer: form.layer,
          state: stateToCheck,
          download_url: form.downloadUrl,
          access_type: form.accessType,
        },
        (event) => {
          if (event.stage === "done" && event.result) {
            const result = event.result;
            setForm((current) => ({
              ...current,
              format: result.format,
              sourceLayer: result.source_layer,
              datasetLayers: result.layers,
              columns: result.field_mapping,
            }));
          } else if (event.stage === "failed") {
            setCheckError(event.error ?? "The link couldn't be checked.");
          } else {
            setCheckProgress(event);
          }
        },
        abort.signal,
      );
    } catch (error) {
      if (abort.signal.aborted) return;
      setCheckError(errorMessage(error));
    }
    setChecking(false);
  }

  /**
   * Pick another layer in the dataset. Fields it doesn't have are cleared.
   */
  function pickDatasetLayer(name: string | null) {
    const fields = form.datasetLayers.find((item) => item.name === name)?.fields ?? [];
    setForm({
      ...form,
      sourceLayer: name,
      columns: Object.fromEntries(
        Object.entries(form.columns).map(([column, field]) => [
          column,
          field !== null && fields.includes(field) ? field : null,
        ]),
      ),
    });
  }

  function submit() {
    if (form.layer === null || form.format === null) return;
    const settings = {
      download_url: form.downloadUrl,
      access_type: form.accessType,
      format: form.format,
      source_layer: form.sourceLayer,
      field_mapping: fieldMapping(form.columns),
      clip_to_state: form.clipToState,
      license: form.license || null,
      attribution: form.attribution || null,
      is_enabled: form.isEnabled,
    };
    if (editing) {
      update.mutate({ sourceId: editing.id, data: settings });
    } else {
      create.mutate({
        data: { layer: form.layer, state: federal ? null : form.state, ...settings },
      });
    }
  }

  const fields =
    form.datasetLayers.find((item) => item.name === (form.sourceLayer ?? ""))?.fields ??
    form.datasetLayers[0]?.fields ??
    [];
  const stateOptions = states.map((state) => ({
    value: state.code,
    label: `${state.name} (${state.code})`,
  }));

  return (
    <Stack>
      {editing ? (
        <Text fw={700}>{sourceName(editing, layers)}</Text>
      ) : (
        <>
          <Select
            label="Layer"
            placeholder="Pick a layer"
            data={layerOptions(layers)}
            value={form.layer}
            onChange={(layer) => changeLink({ layer })}
            searchable
          />
          <Select
            label="State"
            placeholder="Federal or a state"
            data={[{ value: FEDERAL, label: "Federal" }, ...stateOptions]}
            value={form.state}
            onChange={(state) => changeLink({ state })}
            searchable
          />
        </>
      )}

      {federal && (
        <Select
          label="Check with"
          description="The state to fill in the link with when checking it"
          placeholder="Pick a state"
          data={stateOptions}
          value={form.checkState}
          onChange={(checkState) => setForm({ ...form, checkState })}
          searchable
        />
      )}

      <TextInput
        label="Link"
        description="Can hold {state} and {fips}"
        value={form.downloadUrl}
        onChange={(event) => changeLink({ downloadUrl: event.currentTarget.value })}
      />

      <Radio.Group
        label="Type"
        value={form.accessType}
        onChange={(accessType) => changeLink({ accessType })}
      >
        <Group>
          <Radio value="file" label="File" />
          <Radio value="service" label="Service" />
        </Group>
      </Radio.Group>

      <Group>
        <Button
          variant="default"
          onClick={() => void runCheck()}
          disabled={
            checking || form.layer === null || stateToCheck === null || form.downloadUrl === ""
          }
        >
          Check link
        </Button>
      </Group>

      {checking && (
        <Stack gap={4}>
          <Progress
            value={
              checkProgress?.stage === "downloading"
                ? (downloadPercent(
                    checkProgress.bytes_downloaded ?? null,
                    checkProgress.bytes_total ?? null,
                  ) ?? 100)
                : 100
            }
            striped
            animated
            aria-label="Check link progress"
          />
          <Text size="sm">{checkText(checkProgress)}</Text>
        </Stack>
      )}

      {checkError !== null && (
        <Alert color="var(--color-rust)" title="The link couldn't be checked">
          {checkError}
        </Alert>
      )}

      {form.format !== null && (
        <>
          <div>
            <Text size="sm" fw={700}>
              Format
            </Text>
            <Text>{form.format}</Text>
          </div>

          <Select
            label="Dataset layer"
            data={form.datasetLayers.map((item) => item.name).filter(Boolean)}
            value={form.sourceLayer}
            onChange={pickDatasetLayer}
          />

          <Table className={classes.fields} aria-label="Fields">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Column</Table.Th>
                <Table.Th>Field in the data</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {Object.entries(form.columns).map(([column, field]) => (
                <Table.Tr key={column}>
                  <Table.Td>{column}</Table.Td>
                  <Table.Td>
                    <Select
                      aria-label={column}
                      placeholder="No field"
                      data={fields}
                      value={field}
                      onChange={(value) =>
                        setForm({ ...form, columns: { ...form.columns, [column]: value } })
                      }
                      clearable
                    />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}

      <Checkbox
        label="Clip to the state line"
        checked={form.clipToState}
        onChange={(event) => setForm({ ...form, clipToState: event.currentTarget.checked })}
      />
      <TextInput
        label="License"
        value={form.license}
        onChange={(event) => setForm({ ...form, license: event.currentTarget.value })}
      />
      <TextInput
        label="Attribution"
        value={form.attribution}
        onChange={(event) => setForm({ ...form, attribution: event.currentTarget.value })}
      />
      <Checkbox
        label="Enabled"
        description="Loads use only enabled sources"
        checked={form.isEnabled}
        onChange={(event) => setForm({ ...form, isEnabled: event.currentTarget.checked })}
      />

      {save.isError && (
        <Alert color="var(--color-rust)" title="The source wasn't saved">
          {errorMessage(save.error)}
        </Alert>
      )}

      <Group justify="flex-end">
        <Button onClick={submit} disabled={form.format === null} loading={save.isPending}>
          Save
        </Button>
      </Group>
    </Stack>
  );
}

/**
 * Group sources by their layer's group, such as `Water`, in the order the layers come.
 */
function groupSources(sources: SourceRead[], layers: LayerRead[]) {
  const groups = new Map<string, { source: SourceRead; layer: LayerRead | undefined }[]>();
  for (const layer of layers) {
    for (const source of sources.filter((item) => item.layer === layer.name)) {
      groups.set(layer.group, [...(groups.get(layer.group) ?? []), { source, layer }]);
    }
  }
  return [...groups];
}

/**
 * Admin page for the reference database's sources: where each layer downloads from,
 * for one state or for every state.
 *
 * Sources show in one table per group, with the same column widths in every table. Add
 * source and Edit open the source form in a panel on the right.
 */
export function ReferenceSourcesPage() {
  const queryClient = useQueryClient();
  // The source being edited, `new` for Add source, or null when the form is closed.
  const [editing, setEditing] = useState<SourceRead | "new" | null>(null);

  const sources = useReferenceListSources();
  const layers = useReferenceListLayers();
  const states = useReferenceListStates();
  const checks = useReferenceListSourceChecks();
  const runChecks = useReferenceRunSourceChecks({
    mutation: {
      onSuccess: () =>
        queryClient.invalidateQueries({ queryKey: getReferenceListSourceChecksQueryKey() }),
    },
  });

  const allSources = sources.data?.data ?? [];
  const allLayers = layers.data?.data ?? [];
  const allStates = states.data?.data ?? [];
  const lastCheck = checks.data?.data;
  const dateSettings = useDateSettings();
  const layerTitle = (name: string) =>
    allLayers.find((layer) => layer.name === name)?.title ?? name;

  async function saved() {
    setEditing(null);
    await queryClient.invalidateQueries({ queryKey: getReferenceListSourcesQueryKey() });
  }

  return (
    <>
      <header className={classes.header}>
        <Title order={1}>Reference database</Title>
      </header>

      <main className={classes.content}>
        <Group justify="space-between" align="start">
          <Title order={2} className={classes.accent}>
            Sources
          </Title>
          <Group>
            <Anchor component={Link} to="/admin/reference">
              Load layers
            </Anchor>
            <Button onClick={() => setEditing("new")}>Add source</Button>
            <DateSettingsMenu />
          </Group>
        </Group>

        <section className={classes.group}>
          <Group justify="space-between" align="center">
            <Title order={3}>Updates</Title>
            <Button
              variant="default"
              onClick={() => runChecks.mutate()}
              loading={runChecks.isPending}
            >
              Check for updates
            </Button>
          </Group>
          {lastCheck && (
            <Text size="sm">
              {lastCheck.checked_at === null
                ? "Not checked for updates yet"
                : `Last checked ${formatDate(lastCheck.checked_at, dateSettings)}`}
            </Text>
          )}
          {runChecks.isError && (
            <Alert color="var(--color-rust)" title="The check didn't run">
              {errorMessage(runChecks.error)}
            </Alert>
          )}
          {lastCheck?.checked_at && lastCheck.updates.length === 0 && (
            <Text>Every loaded layer is up to date.</Text>
          )}
          {lastCheck && lastCheck.updates.length > 0 && (
            <Table.ScrollContainer minWidth={0} type="native">
              <Table
                withTableBorder
                withColumnBorders
                className={classes.updates}
                aria-label="Updates"
              >
                <Table.Thead>
                  <Table.Tr className={classes.headRow}>
                    <Table.Th>Layer</Table.Th>
                    <Table.Th>State</Table.Th>
                    <Table.Th>Last loaded</Table.Th>
                    <Table.Th>Update</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {lastCheck.updates.map((update) => (
                    <Table.Tr key={`${update.layer}|${update.state}`}>
                      <Table.Th scope="row">{layerTitle(update.layer)}</Table.Th>
                      <Table.Td>{update.state}</Table.Td>
                      <Table.Td>
                        {update.last_pulled === null
                          ? "Never"
                          : formatDate(update.last_pulled, dateSettings)}
                      </Table.Td>
                      <Table.Td>
                        {update.error === null
                          ? "Newer file available"
                          : `Couldn't check: ${update.error}`}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </section>

        {sources.isSuccess && allSources.length === 0 && <Text>No sources yet.</Text>}

        {groupSources(allSources, allLayers).map(([group, rows]) => (
          <section key={group} className={classes.group}>
            <Title order={3}>{group}</Title>
            <Table.ScrollContainer minWidth={0} type="native">
              <Table withTableBorder withColumnBorders className={classes.table} aria-label={group}>
                <colgroup>
                  <col className={classes.layerColumn} />
                  <col className={classes.stateColumn} />
                  <col className={classes.linkColumn} />
                  <col className={classes.formatColumn} />
                  <col className={classes.enabledColumn} />
                  <col className={classes.editColumn} />
                </colgroup>
                <Table.Thead>
                  <Table.Tr className={classes.headRow}>
                    <Table.Th>Layer</Table.Th>
                    <Table.Th>State</Table.Th>
                    <Table.Th>Link</Table.Th>
                    <Table.Th>Format</Table.Th>
                    <Table.Th>Enabled</Table.Th>
                    <Table.Th>
                      <VisuallyHidden>Edit</VisuallyHidden>
                    </Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {rows.map(({ source, layer }) => (
                    <Table.Tr key={source.id}>
                      <Table.Th scope="row">{layer?.title ?? source.layer}</Table.Th>
                      <Table.Td>{source.state ?? "Federal"}</Table.Td>
                      <Table.Td className={classes.link} title={source.download_url}>
                        {source.download_url}
                      </Table.Td>
                      <Table.Td>{source.format}</Table.Td>
                      <Table.Td>{source.is_enabled ? "Yes" : "No"}</Table.Td>
                      <Table.Td>
                        <Button
                          variant="default"
                          size="xs"
                          aria-label={`Edit ${sourceName(source, allLayers)}`}
                          onClick={() => setEditing(source)}
                        >
                          Edit
                        </Button>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </section>
        ))}
      </main>

      <Drawer
        opened={editing !== null}
        onClose={() => setEditing(null)}
        position="right"
        size="lg"
        title={editing === "new" ? "Add source" : "Edit source"}
      >
        {editing !== null && (
          <SourceForm
            key={editing === "new" ? "new" : editing.id}
            editing={editing === "new" ? null : editing}
            layers={allLayers}
            states={allStates}
            onSaved={() => void saved()}
          />
        )}
      </Drawer>
    </>
  );
}
