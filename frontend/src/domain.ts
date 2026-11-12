export function canWithdraw(status: string): boolean {
  return !["Selected", "Rejected", "Withdrawn"].includes(status);
}

export function statusClass(status: string): string {
  return status.toLowerCase().replaceAll(" ", "-");
}
