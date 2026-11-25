import { createFileRoute } from "@tanstack/react-router";

import { ReferenceSourcesPage } from "@/pages/admin/ReferenceSourcesPage";

export const Route = createFileRoute("/admin/reference/sources")({
  component: ReferenceSourcesPage,
});
