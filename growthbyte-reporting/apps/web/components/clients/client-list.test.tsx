import { screen } from "@testing-library/react";

import { jsonResponse, renderWithFreshSWR } from "../test-utils";
import { ClientList } from "./client-list";

describe("ClientList", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("renders distinct de-identified clients with scoped links", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse([
        {
          id: "10000000-0000-4000-8000-000000000001",
          name: "Development Alpha",
          slug: "development-alpha",
          status: "active",
        },
        {
          id: "20000000-0000-4000-8000-000000000002",
          name: "Development Beta",
          slug: "development-beta",
          status: "paused",
        },
      ]),
    );

    renderWithFreshSWR(<ClientList />);

    expect(screen.getByText("Loading clients…")).toBeTruthy();
    expect(await screen.findByText("Development Alpha")).toBeTruthy();
    expect(screen.getByText("Development Beta")).toBeTruthy();
    const links = screen.getAllByRole("link", { name: "Open client" });
    expect(links[0].getAttribute("href")).toContain("000000000001");
    expect(links[1].getAttribute("href")).toContain("000000000002");
  });
});
