import type {
  ReportMetric,
  ReportNumericValue,
  ReportQualityStatus,
  ReportSectionContent,
  SuperKFranchiseReportResponse,
} from "@growthbyte/report-schema";

const PAID_METRICS: readonly (readonly string[])[] = [
  ["spend", "amount_spent"],
  ["reach", "period_reach"],
  ["impressions"],
  ["link_clicks", "clicks"],
  ["ctr", "click_through_rate"],
  ["cpc", "cost_per_click"],
  ["cpm", "cost_per_thousand_impressions"],
  ["meta_reported_leads", "meta_leads"],
];

const FUNNEL_METRICS: readonly (readonly string[])[] = [
  ["operational_leads", "total_leads", "imported_leads"],
  ["rtm_leads"],
  ["cost_per_lead", "cpl"],
  ["rtm_conversion_rate", "rtm_conversion_percent"],
  ["cost_per_rtm"],
  ["click_to_lead_conversion_rate", "click_to_lead_conversion_percent"],
  ["meta_operational_lead_difference", "lead_difference"],
];

const GSC_METRICS: readonly (readonly string[])[] = [
  ["organic_clicks", "gsc_clicks"],
  ["organic_impressions", "gsc_impressions"],
  ["search_ctr", "gsc_ctr", "organic_ctr"],
  ["organic_average_position", "average_position", "gsc_average_position"],
];

const METRIC_LABELS: Readonly<Record<string, string>> = {
  amount_spent: "Amount spent",
  average_position: "Average position",
  click_through_rate: "Click-through rate",
  click_to_lead_conversion_percent: "Click-to-lead conversion",
  click_to_lead_conversion_rate: "Click-to-lead conversion",
  clicks: "Link clicks",
  cost_per_click: "Cost per click",
  cost_per_lead: "Cost per lead",
  cost_per_rtm: "Cost per RTM",
  cost_per_thousand_impressions: "Cost per 1,000 impressions",
  cpc: "Cost per click",
  cpl: "Cost per lead",
  cpm: "Cost per 1,000 impressions",
  ctr: "Click-through rate",
  gsc_average_position: "Average position",
  gsc_clicks: "Organic clicks",
  gsc_ctr: "Search CTR",
  gsc_impressions: "Organic impressions",
  impressions: "Impressions",
  imported_leads: "Operational leads",
  lead_difference: "Meta vs operational difference",
  link_clicks: "Link clicks",
  meta_leads: "Meta-reported leads",
  meta_operational_lead_difference: "Meta vs operational difference",
  meta_reported_leads: "Meta-reported leads",
  operational_leads: "Operational leads",
  organic_clicks: "Organic clicks",
  organic_average_position: "Average position",
  organic_ctr: "Search CTR",
  organic_impressions: "Organic impressions",
  period_reach: "Reach",
  reach: "Reach",
  rtm_conversion_percent: "RTM conversion",
  rtm_conversion_rate: "RTM conversion",
  rtm_leads: "RTM leads",
  search_ctr: "Search CTR",
  spend: "Amount spent",
  total_leads: "Operational leads",
};

function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function metricLabel(metric: ReportMetric): string {
  return METRIC_LABELS[metric.metric_key] || titleCase(metric.metric_key);
}

export function formatReportMetric(
  value: ReportNumericValue | null | undefined,
  unit: string,
  currency?: string | null,
): string {
  if (value === null || value === undefined) {
    return "Unavailable.";
  }

  const numericValue = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numericValue)) {
    return "Unavailable.";
  }

  if (unit === "currency") {
    try {
      return new Intl.NumberFormat("en-IN", {
        currency: currency || "INR",
        maximumFractionDigits: 2,
        minimumFractionDigits: 2,
        style: "currency",
      }).format(numericValue);
    } catch {
      return `${currency || "INR"} ${numericValue.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
    }
  }

  if (unit === "percent") {
    return `${numericValue.toLocaleString("en-IN", { maximumFractionDigits: 2 })}%`;
  }

  if (unit === "position" || unit === "ratio") {
    return numericValue.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }

  return numericValue.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function asFiniteNumber(value: ReportNumericValue | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  const numericValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
}

function formatMetricChange(metric: ReportMetric): string {
  const percentageChange = asFiniteNumber(metric.percentage_change);
  if (percentageChange === null) {
    return formatReportMetric(metric.absolute_change, metric.unit, metric.currency);
  }
  return `${percentageChange > 0 ? "+" : ""}${percentageChange.toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}%`;
}

function formatReportMonth(reportMonth: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(reportMonth);
  if (!match) {
    return reportMonth;
  }
  return new Intl.DateTimeFormat("en", { month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1)),
  );
}

function qualityClasses(status: ReportQualityStatus): string {
  if (status === "verified") {
    return "border-green-700 bg-green-50 text-green-900";
  }
  if (status === "partial") {
    return "border-amber-700 bg-amber-50 text-amber-950";
  }
  return "border-red-700 bg-red-50 text-red-900";
}

function QualityBadge({ status }: Readonly<{ status: ReportQualityStatus }>) {
  return (
    <span
      className={`inline-flex border px-2 py-1 text-xs font-semibold uppercase tracking-wide ${qualityClasses(status)}`}
    >
      {status}
    </span>
  );
}

function selectMetrics(
  metrics: readonly ReportMetric[],
  aliases: readonly (readonly string[])[],
): ReportMetric[] {
  const selected: ReportMetric[] = [];
  const used = new Set<string>();
  for (const keys of aliases) {
    const metric = metrics.find((candidate) => keys.includes(candidate.metric_key));
    if (metric && !used.has(metric.metric_key)) {
      selected.push(metric);
      used.add(metric.metric_key);
    }
  }
  return selected;
}

function MetricGrid({
  emptyMessage,
  metrics,
}: Readonly<{ emptyMessage: string; metrics: readonly ReportMetric[] }>) {
  if (metrics.length === 0) {
    return <p className="border border-dashed border-growthbyte-black/30 p-4">{emptyMessage}</p>;
  }

  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => (
        <div
          className="border border-growthbyte-black/20 bg-growthbyte-white p-4"
          key={metric.metric_key}
        >
          <dt className="text-xs font-semibold uppercase tracking-wide text-growthbyte-black/60">
            {metricLabel(metric)}
          </dt>
          <dd className="mt-2 text-2xl font-bold">
            {formatReportMetric(metric.value, metric.unit, metric.currency)}
          </dd>
          <dd className="mt-2">
            <QualityBadge status={metric.quality_status} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function ReportNarrative({ content }: Readonly<{ content: ReportSectionContent }>) {
  if (content.length === 0) {
    return <p>Unavailable.</p>;
  }

  return (
    <ul className="space-y-3">
      {content.map((item, index) => {
        return (
          <li
            className="border-l-4 border-growthbyte-teal bg-growthbyte-black/[0.03] p-4"
            key={`${item.statement}-${index}`}
          >
            <p className="leading-6">{item.statement}</p>
            {(item.confidence || item.limitation) && (
              <p className="mt-2 text-sm text-growthbyte-black/60">
                Confidence: {item.confidence}. {item.limitation || ""}
              </p>
            )}
            {item.evidence_ids.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {item.evidence_ids.map((evidenceId) => (
                  <code
                    className="break-all bg-growthbyte-white px-2 py-1 text-xs"
                    key={evidenceId}
                  >
                    {evidenceId}
                  </code>
                ))}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function NarrativeSection({
  content,
  title,
}: Readonly<{ content: ReportSectionContent; title: string }>) {
  return (
    <section className="border border-growthbyte-black/20 bg-growthbyte-white p-6">
      <h2 className="text-xl font-bold">{title}</h2>
      <div className="mt-4">
        <ReportNarrative content={content} />
      </div>
    </section>
  );
}

function ComparisonTable({ metrics }: Readonly<{ metrics: readonly ReportMetric[] }>) {
  const comparable = metrics.filter(
    (metric) => metric.previous_value !== null && metric.previous_value !== undefined,
  );

  return (
    <section
      aria-labelledby="comparison-heading"
      className="border border-growthbyte-black/20 bg-growthbyte-white p-6"
    >
      <h2 className="text-xl font-bold" id="comparison-heading">
        Current versus previous month
      </h2>
      {comparable.length === 0 ? (
        <p className="mt-4">Previous-month comparison is unavailable.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b-2 border-growthbyte-black">
                <th className="px-3 py-2">Metric</th>
                <th className="px-3 py-2 text-right">Current</th>
                <th className="px-3 py-2 text-right">Previous</th>
                <th className="px-3 py-2 text-right">Change</th>
              </tr>
            </thead>
            <tbody>
              {comparable.map((metric) => (
                <tr className="border-b border-growthbyte-black/20" key={metric.metric_key}>
                  <th className="px-3 py-3 font-medium">{metricLabel(metric)}</th>
                  <td className="px-3 py-3 text-right">
                    {formatReportMetric(metric.value, metric.unit, metric.currency)}
                  </td>
                  <td className="px-3 py-3 text-right">
                    {formatReportMetric(metric.previous_value, metric.unit, metric.currency)}
                  </td>
                  <td className="px-3 py-3 text-right">{formatMetricChange(metric)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function UnifiedReportView({ report }: Readonly<{ report: SuperKFranchiseReportResponse }>) {
  const metrics = report.monthly_snapshot?.metrics ?? [];
  const paidMetrics = selectMetrics(metrics, PAID_METRICS);
  const funnelMetrics = selectMetrics(metrics, FUNNEL_METRICS);
  const gscMetrics = selectMetrics(metrics, GSC_METRICS);
  const evidence = metrics;
  const sourceEntries = [
    ["Meta Ads", report.sources.meta],
    ["Search Console", report.sources.gsc],
    ["Lead JSON", report.sources.lead_json],
    ["Knowledge", report.sources.knowledge],
    ["KPIs", report.sources.kpis],
  ] as const;

  return (
    <article aria-labelledby="report-title" className="space-y-6" data-testid="unified-report">
      <header className="border border-growthbyte-black bg-growthbyte-black p-6 text-growthbyte-white">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <p className="font-semibold uppercase tracking-[0.18em] text-growthbyte-amber">
              SuperK Franchise
            </p>
            <h1 className="mt-2 text-3xl font-bold" id="report-title">
              Monthly performance report
            </h1>
            <p className="mt-2 text-growthbyte-white/80">
              {formatReportMonth(report.report_month)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <QualityBadge status={report.quality_status} />
            <span className="border border-growthbyte-white/40 px-2 py-1 text-xs font-semibold uppercase tracking-wide">
              {report.report_status.replace(/_/g, " ")}
            </span>
          </div>
        </div>
        <dl className="mt-6 grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-growthbyte-white/60">Snapshot</dt>
            <dd className="mt-1 break-all font-mono">{report.snapshot_id || "Unavailable."}</dd>
          </div>
          <div>
            <dt className="text-growthbyte-white/60">Formula version</dt>
            <dd className="mt-1 font-mono">
              {report.monthly_snapshot?.formula_version || "Unavailable."}
            </dd>
          </div>
          <div>
            <dt className="text-growthbyte-white/60">Snapshot result</dt>
            <dd className="mt-1">
              {report.snapshot_reused ? "Reused unchanged inputs" : "New snapshot"}
            </dd>
          </div>
        </dl>
      </header>

      {report.warnings.length > 0 && (
        <section
          aria-labelledby="quality-warning-heading"
          className="border border-amber-700 bg-amber-50 p-5"
        >
          <h2 className="font-bold text-amber-950" id="quality-warning-heading">
            Data-quality warnings
          </h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-amber-950">
            {report.warnings.map((warning) => (
              <li key={`${warning.code}-${warning.message}`}>{warning.message}</li>
            ))}
          </ul>
        </section>
      )}

      <NarrativeSection content={report.sections.executive_summary} title="Executive summary" />
      <ComparisonTable metrics={metrics} />

      <section
        aria-labelledby="paid-heading"
        className="space-y-4 border border-growthbyte-black/20 bg-growthbyte-black/[0.02] p-6"
      >
        <h2 className="text-xl font-bold" id="paid-heading">
          Paid performance
        </h2>
        <MetricGrid
          emptyMessage="Paid-performance metrics are unavailable."
          metrics={paidMetrics}
        />
        <ReportNarrative content={report.sections.paid_performance_summary} />
      </section>

      <section
        aria-labelledby="funnel-heading"
        className="space-y-4 border border-growthbyte-black/20 bg-growthbyte-black/[0.02] p-6"
      >
        <h2 className="text-xl font-bold" id="funnel-heading">
          Lead and RTM funnel
        </h2>
        <MetricGrid emptyMessage="Lead and RTM metrics are unavailable." metrics={funnelMetrics} />
        <ReportNarrative content={report.sections.lead_and_rtm_funnel} />
      </section>

      <section
        aria-labelledby="gsc-heading"
        className="space-y-4 border border-growthbyte-black/20 bg-growthbyte-black/[0.02] p-6"
      >
        <h2 className="text-xl font-bold" id="gsc-heading">
          Google Search Console
        </h2>
        <MetricGrid emptyMessage="Search Console metrics are unavailable." metrics={gscMetrics} />
        <ReportNarrative content={report.sections.search_console_seo_summary} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <NarrativeSection
          content={report.sections.campaign_and_creative_observations}
          title="Campaign and creative observations"
        />
        <NarrativeSection
          content={report.sections.search_query_and_page_movements}
          title="Search query and page movements"
        />
        <NarrativeSection content={report.sections.important_wins} title="Important wins" />
        <NarrativeSection content={report.sections.important_problems} title="Important problems" />
      </div>

      <NarrativeSection content={report.sections.recommended_actions} title="Recommended actions" />

      <section
        aria-labelledby="reconciliation-heading"
        className="border border-growthbyte-black/20 bg-growthbyte-white p-6"
      >
        <h2 className="text-xl font-bold" id="reconciliation-heading">
          Data reconciliation and limitations
        </h2>
        <dl className="mt-4 grid gap-px bg-growthbyte-black sm:grid-cols-5">
          {sourceEntries.map(([label, source]) => (
            <div className="bg-growthbyte-white p-3" key={label}>
              <dt className="text-xs font-semibold uppercase tracking-wide text-growthbyte-black/60">
                {label}
              </dt>
              <dd className="mt-1 font-medium">{titleCase(source.status)}</dd>
              {source.detail && (
                <dd className="mt-1 text-xs text-growthbyte-black/60">{source.detail}</dd>
              )}
            </div>
          ))}
        </dl>
        <div className="mt-5">
          <ReportNarrative content={report.sections.data_reconciliation_and_limitations} />
        </div>
      </section>

      <section
        aria-labelledby="evidence-heading"
        className="border border-growthbyte-black/20 bg-growthbyte-white p-6"
      >
        <h2 className="text-xl font-bold" id="evidence-heading">
          Evidence references
        </h2>
        {evidence.length === 0 ? (
          <p className="mt-4">No evidence references are available.</p>
        ) : (
          <ul className="mt-4 space-y-2">
            {evidence.map((item) => (
              <li className="border border-growthbyte-black/10 p-3" key={item.evidence_id}>
                <code className="break-all text-xs">{item.evidence_id}</code>
                <span className="ml-2 text-sm">{metricLabel(item)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {report.report_status === "approved" && report.pdf?.download_url && (
        <div className="flex justify-end">
          <a
            className="border border-growthbyte-black bg-growthbyte-black px-5 py-3 font-semibold text-growthbyte-white hover:bg-growthbyte-teal"
            href={report.pdf.download_url}
          >
            Download PDF
          </a>
        </div>
      )}
    </article>
  );
}
