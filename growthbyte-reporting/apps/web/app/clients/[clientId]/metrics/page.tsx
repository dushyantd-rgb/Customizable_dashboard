'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

import { api, safeErrorMessage } from '@/lib/api-client';
import { LoadingState } from '@/components/async-state';

interface MetricValue {
  metric_key: string;
  value: number | null;
  numerator: number | null;
  denominator: number | null;
  unit: string;
  currency: string | null;
  quality_status: string;
  quality_reasons: string[];
}

interface MetricsData {
  client_id: string;
  period_start: string;
  period_end: string;
  currency: string;
  formula_version: string;
  input_cutoff_at: string;
  metrics: MetricValue[];
  unmatched_count: number;
  quality_warnings: string[];
}

interface Snapshot {
  id: string;
  metric_key: string;
  calculated_at: string;
}

export default function MetricsPage() {
  const params = useParams();
  const clientId = params.clientId as string;

  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Date range inputs - seeded data uses January 2024
  const [periodStart, setPeriodStart] = useState('2024-01-01');
  const [periodEnd, setPeriodEnd] = useState('2024-01-31');

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.getMetrics(clientId, periodStart, periodEnd);
      setMetrics(data as MetricsData);
    } catch (err) {
      setError(safeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const generateSnapshots = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await api.generateSnapshot(clientId, periodStart, periodEnd);
      setSuccess(`Generated ${result.snapshot_count} snapshots`);
      // Automatically fetch snapshots after generation
      await fetchSnapshots();
    } catch (err) {
      setError(safeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const fetchSnapshots = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.listSnapshots(clientId);
      setSnapshots(data as Snapshot[]);
    } catch (err) {
      setError(safeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const [success, setSuccess] = useState<string | null>(null);

  const formatMetricValue = (metric: MetricValue): string => {
    if (metric.value === null) return 'N/A';

    if (metric.unit === 'currency') {
      return `${metric.currency || 'USD'} ${metric.value.toFixed(2)}`;
    }

    if (metric.unit === 'percent') {
      return `${metric.value.toFixed(2)}%`;
    }

    return metric.value.toLocaleString();
  };

  const getMetricLabel = (key: string): string => {
    const labels: Record<string, string> = {
      spend: 'Total Spend',
      impressions: 'Impressions',
      reach: 'Reach',
      clicks: 'Clicks',
      meta_leads: 'Meta Leads',
      imported_leads: 'Imported Leads',
      qualified_leads: 'Qualified Leads',
      disqualified_leads: 'Disqualified Leads',
      invalid_leads: 'Invalid Leads',
      converted_leads: 'Converted Leads',
      cost_per_lead: 'Cost Per Lead',
      cost_per_qualified_lead: 'Cost Per Qualified Lead',
      qualification_rate: 'Qualification Rate',
      conversion_rate: 'Conversion Rate',
      ctr: 'Click-Through Rate',
      cpc: 'Cost Per Click',
      cpm: 'Cost Per Mille',
      unmatched_leads: 'Unmatched Leads',
      attribution_coverage: 'Attribution Coverage',
    };
    return labels[key] || key.replace(/_/g, ' ');
  };

  if (loading && !metrics && !snapshots.length) {
    return <LoadingState label="Loading metrics..." />;
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <Link
          href={`/clients/${encodeURIComponent(clientId)}`}
          className="text-growthbyte-teal underline hover:no-underline"
        >
          ← Back to client
        </Link>
      </div>

      <h1 className="text-2xl font-bold mb-6">Metrics Dashboard</h1>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
          {success}
        </div>
      )}

      {/* Date Range Inputs */}
      <div className="flex flex-wrap gap-4 items-end mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Period Start</label>
          <input
            type="date"
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
            className="border rounded px-3 py-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Period End</label>
          <input
            type="date"
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
            className="border rounded px-3 py-2"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={fetchMetrics}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50 hover:bg-blue-700"
          >
            {loading ? 'Loading...' : 'Preview Metrics'}
          </button>
          <button
            onClick={generateSnapshots}
            disabled={loading}
            className="bg-green-600 text-white px-4 py-2 rounded disabled:opacity-50 hover:bg-green-700"
          >
            Generate Snapshots
          </button>
          <button
            onClick={fetchSnapshots}
            disabled={loading}
            className="bg-gray-600 text-white px-4 py-2 rounded disabled:opacity-50 hover:bg-gray-700"
          >
            List Snapshots
          </button>
        </div>
      </div>

      {/* Metrics Display */}
      {metrics && (
        <div className="mb-8">
          <div className="bg-gray-100 p-4 rounded mb-4">
            <p className="text-sm text-gray-600">
              Currency: <strong>{metrics.currency}</strong> | Formula Version:{' '}
              <strong>{metrics.formula_version}</strong>
            </p>
            <p className="text-sm text-gray-600">
              Period: {new Date(metrics.period_start).toLocaleDateString()} -{' '}
              {new Date(metrics.period_end).toLocaleDateString()}
            </p>
          </div>

          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {metrics.metrics
              .filter((m) =>
                ['spend', 'meta_leads', 'qualified_leads', 'cost_per_lead'].includes(m.metric_key)
              )
              .map((metric) => (
                <div key={metric.metric_key} className="bg-white shadow rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-500">
                    {getMetricLabel(metric.metric_key)}
                  </h3>
                  <p className="text-2xl font-bold">
                    {metric.quality_status === 'unavailable' ? (
                      <span className="text-gray-400">N/A</span>
                    ) : (
                      formatMetricValue(metric)
                    )}
                  </p>
                  {metric.quality_reasons.length > 0 && (
                    <p className="text-xs text-yellow-600">{metric.quality_reasons.join(', ')}</p>
                  )}
                </div>
              ))}
          </div>

          {/* Attribution Coverage */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <h3 className="text-lg font-semibold mb-2">Attribution Coverage</h3>
            <div className="flex items-center gap-4">
              <div className="text-3xl font-bold text-blue-600">
                {metrics.metrics.find((m) => m.metric_key === 'attribution_coverage')?.value?.toFixed(
                  1
                ) || 'N/A'}
                %
              </div>
              <div className="text-gray-600">
                <p>Unmatched Leads: {metrics.unmatched_count}</p>
              </div>
            </div>
          </div>

          {/* Full Metrics Table */}
          <h3 className="text-lg font-semibold mb-2">All Metrics</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full bg-white border">
              <thead>
                <tr className="bg-gray-100">
                  <th className="px-4 py-2 text-left">Metric</th>
                  <th className="px-4 py-2 text-right">Value</th>
                  <th className="px-4 py-2 text-right">Numerator</th>
                  <th className="px-4 py-2 text-right">Denominator</th>
                  <th className="px-4 py-2 text-left">Quality</th>
                </tr>
              </thead>
              <tbody>
                {metrics.metrics.map((metric) => (
                  <tr key={metric.metric_key} className="border-t">
                    <td className="px-4 py-2">{getMetricLabel(metric.metric_key)}</td>
                    <td className="px-4 py-2 text-right">
                      {metric.quality_status === 'unavailable' ? (
                        <span className="text-gray-400">N/A</span>
                      ) : (
                        formatMetricValue(metric)
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {metric.numerator !== null ? metric.numerator.toFixed(2) : '-'}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {metric.denominator !== null ? metric.denominator.toFixed(2) : '-'}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          metric.quality_status === 'verified'
                            ? 'bg-green-100 text-green-800'
                            : metric.quality_status === 'partial'
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {metric.quality_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Snapshots List */}
      {snapshots.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Existing Snapshots</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full bg-white border">
              <thead>
                <tr className="bg-gray-100">
                  <th className="px-4 py-2 text-left">ID</th>
                  <th className="px-4 py-2 text-left">Metric</th>
                  <th className="px-4 py-2 text-left">Calculated At</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((snapshot) => (
                  <tr key={snapshot.id} className="border-t">
                    <td className="px-4 py-2 text-xs font-mono">{snapshot.id.slice(0, 8)}...</td>
                    <td className="px-4 py-2">{snapshot.metric_key}</td>
                    <td className="px-4 py-2">
                      {new Date(snapshot.calculated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!metrics && !snapshots.length && !loading && (
        <div className="text-gray-600">
          Select a date range and click &quot;Preview Metrics&quot; to view calculated metrics, or &quot;List Snapshots&quot; to view saved snapshots.
        </div>
      )}
    </div>
  );
}
