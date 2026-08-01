import { SuperKReportGenerator } from "../../../../../components/reports/superk-report-generator";

interface SuperKFranchiseReportPageProps {
  readonly params: Promise<{ clientId: string }>;
}

export default async function SuperKFranchiseReportPage({
  params,
}: SuperKFranchiseReportPageProps) {
  const { clientId } = await params;
  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <SuperKReportGenerator clientId={clientId} />
    </main>
  );
}
