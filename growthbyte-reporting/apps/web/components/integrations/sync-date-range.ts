export interface SyncDateRange {
  readonly dateFrom: string;
  readonly dateTo: string;
}

export function currentMonthToDate(now = new Date()): SyncDateRange {
  const year = now.getFullYear();
  const month = now.getMonth();
  return {
    dateFrom: formatLocalDate(new Date(year, month, 1)),
    dateTo: formatLocalDate(now),
  };
}

function formatLocalDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
