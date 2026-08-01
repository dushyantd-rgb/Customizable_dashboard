'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

import { api, safeErrorMessage } from '@/lib/api-client';
import { LoadingState } from '@/components/async-state';

interface UnmatchedLead {
  id: string;
  source_lead_id: string | null;
  lead_at: string | null;
  campaign_name: string | null;
  adset_name: string | null;
  ad_name: string | null;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  source_status_raw: string | null;
  canonical_status: string;
  match_candidates: Array<{
    entity_level: string;
    external_entity_id: string;
    entity_display_name: string | null;
  }>;
  candidate_count: number;
}

export default function MatchingPage() {
  const params = useParams();
  const clientId = params.clientId as string;

  const [unmatchedLeads, setUnmatchedLeads] = useState<UnmatchedLead[]>([]);
  const [ambiguousLeads, setAmbiguousLeads] = useState<UnmatchedLead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const runNormalisation = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await api.runNormalisation(clientId);
      setSuccess(`Normalisation complete: ${result.normalised} normalised, ${result.skipped} skipped`);
    } catch (err) {
      setError(safeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const runMatching = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await api.runMatching(clientId);
      setSuccess(
        `Matching complete: ${result.matched} matched, ${result.ambiguous} ambiguous, ${result.unmatched} unmatched`
      );
    } catch (err) {
      setError(safeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const loadUnmatched = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.listUnmatchedLeads(clientId);
      setUnmatchedLeads(data as UnmatchedLead[]);
    } catch (err) {
      setError(safeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const loadAmbiguous = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.listAmbiguousLeads(clientId);
      setAmbiguousLeads(data as UnmatchedLead[]);
    } catch (err) {
      setError(safeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  if (loading && !unmatchedLeads.length && !ambiguousLeads.length) {
    return <LoadingState label="Loading matching data..." />;
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

      <h1 className="text-2xl font-bold mb-6">Lead Matching</h1>

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

      <div className="flex flex-wrap gap-4 mb-6">
        <button
          onClick={runNormalisation}
          disabled={loading}
          className="bg-purple-600 text-white px-4 py-2 rounded disabled:opacity-50 hover:bg-purple-700"
        >
          {loading ? 'Running...' : 'Run Normalisation'}
        </button>

        <button
          onClick={runMatching}
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50 hover:bg-blue-700"
        >
          {loading ? 'Running...' : 'Run Matching'}
        </button>

        <button
          onClick={loadUnmatched}
          disabled={loading}
          className="bg-gray-600 text-white px-4 py-2 rounded disabled:opacity-50 hover:bg-gray-700"
        >
          Load Unmatched
        </button>

        <button
          onClick={loadAmbiguous}
          disabled={loading}
          className="bg-yellow-600 text-white px-4 py-2 rounded disabled:opacity-50 hover:bg-yellow-700"
        >
          Load Ambiguous
        </button>
      </div>

      {unmatchedLeads.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">
            Unmatched Leads ({unmatchedLeads.length})
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full bg-white border">
              <thead>
                <tr className="bg-gray-100">
                  <th className="px-4 py-2 text-left">ID</th>
                  <th className="px-4 py-2 text-left">Lead At</th>
                  <th className="px-4 py-2 text-left">Campaign</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Candidates</th>
                </tr>
              </thead>
              <tbody>
                {unmatchedLeads.map((lead) => (
                  <tr key={lead.id} className="border-t">
                    <td className="px-4 py-2 text-xs font-mono">{lead.id.slice(0, 8)}...</td>
                    <td className="px-4 py-2">
                      {lead.lead_at ? new Date(lead.lead_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-4 py-2">{lead.campaign_name || '-'}</td>
                    <td className="px-4 py-2">{lead.canonical_status}</td>
                    <td className="px-4 py-2">
                      {lead.candidate_count > 0 ? (
                        <span className="text-blue-600">{lead.candidate_count} candidates</span>
                      ) : (
                        <span className="text-gray-400">None</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {ambiguousLeads.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">
            Ambiguous Leads ({ambiguousLeads.length})
          </h2>
          <p className="text-gray-600 mb-2">
            These leads have multiple match candidates and require manual review.
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full bg-white border">
              <thead>
                <tr className="bg-yellow-100">
                  <th className="px-4 py-2 text-left">ID</th>
                  <th className="px-4 py-2 text-left">Campaign Name</th>
                  <th className="px-4 py-2 text-left">Candidates</th>
                </tr>
              </thead>
              <tbody>
                {ambiguousLeads.map((lead) => (
                  <tr key={lead.id} className="border-t">
                    <td className="px-4 py-2 text-xs font-mono">{lead.id.slice(0, 8)}...</td>
                    <td className="px-4 py-2">{lead.campaign_name || '-'}</td>
                    <td className="px-4 py-2">
                      <ul className="list-disc list-inside">
                        {lead.match_candidates.map((c, i) => (
                          <li key={i}>
                            {c.entity_level}: {c.entity_display_name || c.external_entity_id}
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!unmatchedLeads.length && !ambiguousLeads.length && !loading && (
        <div className="text-gray-600">
          Click the buttons above to run normalisation/matching or load lead data.
        </div>
      )}
    </div>
  );
}
