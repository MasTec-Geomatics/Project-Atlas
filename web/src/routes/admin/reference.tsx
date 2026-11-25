import { createFileRoute } from "@tanstack/react-router";

import { ReferenceAdminPage } from "@/pages/admin/ReferenceAdminPage";

export const Route = createFileRoute("/admin/reference")({
  component: ReferenceAdminPage,
});
