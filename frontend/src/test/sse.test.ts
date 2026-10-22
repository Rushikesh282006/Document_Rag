import { describe, expect, it } from "vitest";
import { parseSSE, normalizeSources } from "@/lib/api";

describe("parseSSE", () => {
  it("splits complete events and keeps the partial tail", () => {
    const { events, rest } = parseSSE('event: sources\ndata: [{"a":1}]\n\nevent: token\ndata: Hel\n\nevent: tok');
    expect(events).toEqual([{ event: "sources", data: '[{"a":1}]' }, { event: "token", data: "Hel" }]);
    expect(rest).toBe("event: tok");
  });
  it("recognises end events without data", () => {
    expect(parseSSE("event: end\n\n").events).toEqual([{ event: "end", data: "" }]);
  });
});

describe("normalizeSources", () => {
  it("handles backend citations response format", () => {
    const backendData = {
      citations: [
        {
          document_id: "doc-123",
          filename: "test.pdf",
          page_number: 3,
          content_preview: "Sample text preview",
          score: 0.95,
        },
      ],
    };
    const sources = normalizeSources(backendData);
    expect(sources).toHaveLength(1);
    expect(sources[0]).toEqual({
      document_id: "doc-123",
      document_name: "test.pdf",
      page: 3,
      snippet: "Sample text preview",
      score: 0.95,
    });
  });
});
