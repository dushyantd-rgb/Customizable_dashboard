import { render, screen } from "@testing-library/react";

import HomePage from "./page";

describe("HomePage", () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({ service: "api", status: "ok", version: "0.1.0" }),
      ok: true,
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("renders the platform identity and API health", async () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "GrowthByte Reporting Platform" })).toBeTruthy();
    expect(await screen.findByText("API responding")).toBeTruthy();
  });
});
