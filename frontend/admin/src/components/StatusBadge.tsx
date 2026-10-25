import type { Pass2Status } from "../../shared/types.ts";

// text-bg-secondary-subtle (Bootstrap's auto-tinted light variant) renders
// near-invisible text against this project's muted-brown custom $secondary
// -- the tint/shade mixins assume a more saturated input color. Solid
// text-bg-* variants compute readable contrast reliably instead.
const VARIANT: Record<Pass2Status, string> = {
  pending: "text-bg-secondary",
  accepted: "text-bg-success",
  rejected: "text-bg-danger",
  flagged_hard: "text-bg-warning",
};

const LABEL: Record<Pass2Status, string> = {
  pending: "pending",
  accepted: "accepted",
  rejected: "rejected",
  flagged_hard: "flagged",
};

export function StatusBadge({ status }: { status: Pass2Status }) {
  return <span className={`badge rounded-pill ${VARIANT[status]}`}>{LABEL[status]}</span>;
}
