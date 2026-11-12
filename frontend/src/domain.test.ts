import { describe, expect, it } from "vitest";
import { canWithdraw, statusClass } from "./domain";

describe("application status helpers", () => {
  it("allows withdrawal only for active applications", () => {
    expect(canWithdraw("Applied")).toBe(true);
    expect(canWithdraw("Interview Scheduled")).toBe(true);
    expect(canWithdraw("Selected")).toBe(false);
    expect(canWithdraw("Rejected")).toBe(false);
    expect(canWithdraw("Withdrawn")).toBe(false);
  });

  it("creates a CSS class from a multi-word status", () => {
    expect(statusClass("Under Review")).toBe("under-review");
  });
});
