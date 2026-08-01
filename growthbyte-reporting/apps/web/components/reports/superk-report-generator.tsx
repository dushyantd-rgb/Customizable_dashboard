"use client";

import type { SuperKFranchiseReportResponse } from "@growthbyte/report-schema";
import Link from "next/link";
import { useState } from "react";

import { api, safeErrorMessage } from "../../lib/api-client";
import { ErrorState } from "../async-state";
import { UnifiedReportView } from "./unified-report-view";

type Vertical = "b2b" | "qcom" | "b2c";

const VERTICAL_CONFIG = {
  b2b: {
    name: "B2B Franchise",
    description: "Lead generation and RTM funnel metrics",
  },
  qcom: {
    name: "QCOM E-commerce",
    description: "Purchase and ROAS metrics for e-commerce",
  },
  b2c: {
    name: "B2C Consumer",
    description: "Consumer purchase and value metrics",
  },
};

export function SuperKReportGenerator({ clientId }: Readonly<{ clientId: string }>) {
  const [report, setReport] = useState<SuperKFranchiseReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedVertical, setSelectedVertical] = useState<Vertical>("b2b");
  const [agentThinking, setAgentThinking] = useState<string>("");

  const generateReport = async () => {
    setError(null);
    setReport(null);
    setIsGenerating(true);
    setAgentThinking("Initializing AI agent...");

    try {
      // Simulate AI agent thinking process
      await new Promise(resolve => setTimeout(resolve, 500));
      setAgentThinking(`Analyzing ${VERTICAL_CONFIG[selectedVertical].name} data...`);

      await new Promise(resolve => setTimeout(resolve, 800));
      setAgentThinking("Fetching Meta Ads insights...");

      await new Promise(resolve => setTimeout(resolve, 600));
      setAgentThinking("Calculating vertical-specific metrics...");

      await new Promise(resolve => setTimeout(resolve, 700));
      setAgentThinking("Generating AI-powered recommendations...");

      const response = await api.generateSuperKFranchiseReport(clientId, selectedVertical);

      setAgentThinking("Finalizing report...");
      await new Promise(resolve => setTimeout(resolve, 400));

      setReport(response);
    } catch (generationError) {
      setError(safeErrorMessage(generationError));
    } finally {
      setIsGenerating(false);
      setAgentThinking("");
    }
  };

  return (
    <div className="space-y-8">
      <Link
        className="text-sm font-medium text-growthbyte-teal underline underline-offset-4"
        href={`/clients/${encodeURIComponent(clientId)}`}
      >
        Back to client
      </Link>

      {!report && (
        <section className="border border-growthbyte-black bg-growthbyte-white p-8 text-center">
          <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
            SuperK Franchise
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">AI-Powered Unified Monthly Report</h1>
          <p className="mx-auto mt-4 max-w-2xl text-growthbyte-black/70">
            Select your reporting vertical and let the AI agent generate comprehensive insights
            with narrative recommendations.
          </p>

          {/* Vertical Selection Dropdown */}
          <div className="mx-auto mt-8 max-w-md">
            <label htmlFor="vertical-select" className="block text-left text-sm font-medium text-growthbyte-black/70">
              Report Vertical
            </label>
            <select
              id="vertical-select"
              value={selectedVertical}
              onChange={(e) => setSelectedVertical(e.target.value as Vertical)}
              className="mt-2 block w-full rounded-md border border-growthbyte-black/30 bg-white px-4 py-3 text-left text-base focus:border-growthbyte-teal focus:outline-none focus:ring-1 focus:ring-growthbyte-teal"
              disabled={isGenerating}
            >
              <option value="b2b">{VERTICAL_CONFIG.b2b.name} - {VERTICAL_CONFIG.b2b.description}</option>
              <option value="qcom">{VERTICAL_CONFIG.qcom.name} - {VERTICAL_CONFIG.qcom.description}</option>
              <option value="b2c">{VERTICAL_CONFIG.b2c.name} - {VERTICAL_CONFIG.b2c.description}</option>
            </select>
          </div>

          {/* Vertical Description */}
          <div className="mt-4 rounded-md bg-growthbyte-amber/10 p-4 text-left">
            <h3 className="font-semibold text-growthbyte-black">
              {VERTICAL_CONFIG[selectedVertical].name} Metrics:
            </h3>
            <div className="mt-2 grid grid-cols-2 gap-4 text-sm">
              {selectedVertical === "b2b" && (
                <>
                  <div>
                    <p className="font-medium text-growthbyte-teal">Input Metrics:</p>
                    <ul className="mt-1 text-growthbyte-black/70">
                      <li>• Amount spent</li>
                      <li>• Reach</li>
                      <li>• Impressions</li>
                      <li>• Link clicks</li>
                      <li>• CPC, CPM, CTR</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-growthbyte-teal">Output Metrics:</p>
                    <ul className="mt-1 text-growthbyte-black/70">
                      <li>• Leads</li>
                      <li>• Cost per lead</li>
                      <li>• Conversion %</li>
                      <li>• RTM Leads</li>
                      <li>• Cost per RTM</li>
                    </ul>
                  </div>
                </>
              )}
              {selectedVertical === "qcom" && (
                <>
                  <div>
                    <p className="font-medium text-growthbyte-teal">Input Metrics:</p>
                    <ul className="mt-1 text-growthbyte-black/70">
                      <li>• Amount spent</li>
                      <li>• Reach</li>
                      <li>• Impressions</li>
                      <li>• Link clicks</li>
                      <li>• CPC, CPM, CTR</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-growthbyte-teal">Output Metrics:</p>
                    <ul className="mt-1 text-growthbyte-black/70">
                      <li>• Purchases</li>
                      <li>• Cost per purchase</li>
                      <li>• Conversion %</li>
                      <li>• Purchase ROAS</li>
                      <li>• Comment/log</li>
                    </ul>
                  </div>
                </>
              )}
              {selectedVertical === "b2c" && (
                <>
                  <div>
                    <p className="font-medium text-growthbyte-teal">Input Metrics:</p>
                    <ul className="mt-1 text-growthbyte-black/70">
                      <li>• Amount spent</li>
                      <li>• Reach</li>
                      <li>• Impressions</li>
                      <li>• Link clicks</li>
                      <li>• CPC, CPM, CTR</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-growthbyte-teal">Output Metrics:</p>
                    <ul className="mt-1 text-growthbyte-black/70">
                      <li>• Purchases</li>
                      <li>• Purchase value</li>
                      <li>• Conversion %</li>
                      <li>• ROAS</li>
                      <li>• Comment/log</li>
                    </ul>
                  </div>
                </>
              )}
            </div>
          </div>

          {error && (
            <div className="mt-6 text-left">
              <ErrorState message={error} />
            </div>
          )}

          {/* AI Agent Thinking Indicator */}
          {isGenerating && (
            <div className="mt-6 rounded-md bg-growthbyte-teal/10 p-6">
              <div className="flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-growthbyte-teal border-r-transparent"></div>
                <span className="ml-3 font-medium text-growthbyte-teal">
                  {agentThinking}
                </span>
              </div>
              <p className="mt-3 text-sm text-growthbyte-black/60">
                AI agent is analyzing data and generating insights...
              </p>
            </div>
          )}

          <button
            aria-busy={isGenerating}
            className="primary-button mt-8 min-w-48"
            disabled={isGenerating}
            onClick={generateReport}
            type="button"
          >
            {isGenerating ? "AI Agent Working..." : "Generate AI-Powered Report"}
          </button>

          {!isGenerating && (
            <p className="mt-4 text-sm text-growthbyte-black/60" role="status">
              AI agent will sync verified sources, calculate metrics, and generate narrative recommendations
            </p>
          )}
        </section>
      )}

      {report && <UnifiedReportView report={report} />}
    </div>
  );
}
