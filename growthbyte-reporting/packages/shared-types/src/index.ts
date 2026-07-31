export type HealthStatus = "ok" | "ready";

export interface ServiceHealth {
  readonly service: "api" | "mcp" | "web";
  readonly status: HealthStatus;
  readonly version: string;
}
