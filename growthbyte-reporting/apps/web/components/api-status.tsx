"use client";

import type { ServiceHealth } from "@growthbyte/shared-types";
import { StatusCard } from "@growthbyte/ui";
import { useEffect, useState } from "react";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type ApiState = "checking" | "healthy" | "unavailable";

export function APIStatus() {
  const [state, setState] = useState<ApiState>("checking");

  useEffect(() => {
    const controller = new AbortController();

    async function checkHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          cache: "no-store",
          signal: controller.signal,
        });
        const payload = (await response.json()) as ServiceHealth;
        setState(response.ok && payload.status === "ok" ? "healthy" : "unavailable");
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setState("unavailable");
        }
      }
    }

    void checkHealth();
    return () => controller.abort();
  }, []);

  const content = {
    checking: { detail: "Checking the FastAPI service.", label: "Checking API" },
    healthy: {
      detail: "The FastAPI health endpoint responded successfully.",
      label: "API responding",
    },
    unavailable: {
      detail: "Start the API on port 8000 to complete the local health check.",
      label: "API unavailable",
    },
  }[state];

  return <StatusCard detail={content.detail} label={content.label} healthy={state === "healthy"} />;
}
