import { api, SafeApiError } from "./api-client";

describe("API client", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("surfaces only the backend safe-error contract", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({
        error: { code: "client_not_found", message: "Client was not found" },
      }),
      ok: false,
    });

    await expect(api.getClient("client-a")).rejects.toEqual(
      expect.objectContaining<Partial<SafeApiError>>({
        code: "client_not_found",
        message: "Client was not found",
      }),
    );
  });

  it("does not expose an unstructured backend response", async () => {
    const rawDetail = "database=https://private.example.test service_role=secret";
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({ detail: rawDetail }),
      ok: false,
    });

    await expect(api.listClients()).rejects.toThrow(
      "The request could not be completed. Please try again.",
    );
    try {
      await api.listClients();
    } catch (error) {
      expect(String(error)).not.toContain(rawDetail);
    }
  });

  it("keeps client scope in the path and out of mutation data", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      json: async () => ({}),
      ok: true,
    });
    global.fetch = fetchMock;

    await api.updateKnowledge("client/a", "record?one", {
      status: "approved",
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/clients/client%2Fa/knowledge/record%3Fone");
    expect(JSON.parse(String(init.body))).toEqual({ status: "approved" });
    expect(String(init.body)).not.toContain("client_id");
  });
});
