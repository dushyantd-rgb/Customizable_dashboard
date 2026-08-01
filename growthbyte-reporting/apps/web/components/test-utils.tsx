import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { SWRConfig } from "swr";

export function renderWithFreshSWR(component: ReactElement) {
  return render(
    <SWRConfig
      value={{
        dedupingInterval: 0,
        provider: () => new Map(),
        shouldRetryOnError: false,
      }}
    >
      {component}
    </SWRConfig>,
  );
}

export function jsonResponse(payload: unknown, ok = true): Response {
  return {
    json: async () => payload,
    ok,
    status: ok ? 200 : 500,
  } as Response;
}
