import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dashboard } from "../pages/Dashboard";

describe("verification workspace", () => {
  beforeEach(() =>
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ status: "ok", service: "proofloop" })),
        ),
    ),
  );
  it("labels fixture evidence and prevents execution from the preview", async () => {
    render(<Dashboard />);
    expect(screen.getByText(/Illustrative contract data/)).toBeTruthy();
    expect(
      (
        screen.getByRole("button", {
          name: "Start verification",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(
      (
        screen.getByRole("button", {
          name: "Challenge again",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(screen.getByText(/Illustrative counts/)).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByText("Backend connected")).toBeTruthy(),
    );
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("allows keyboard navigation to exact code changes", async () => {
    const user = userEvent.setup();
    render(<Dashboard />);
    const first = screen.getByRole("tab", { name: "Verification" });
    first.focus();
    await user.keyboard("{ArrowRight}");
    const diffTab = screen.getByRole("tab", { name: "Code changes" });
    expect(diffTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByLabelText("Patch code changes")).toBeTruthy();
    expect(document.activeElement).toBe(diffTab);
  });
  it("shows a real backend error and never falls back to fixture results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          url.endsWith("/health")
            ? new Response(
                JSON.stringify({ status: "ok", service: "proofloop" }),
              )
            : new Response("secret upstream detail", { status: 503 }),
        ),
      ),
    );
    const user = userEvent.setup();
    render(<Dashboard />);
    await waitFor(() => screen.getByText("Backend connected"));
    await user.click(screen.getByRole("button", { name: "Live" }));
    expect(
      screen.getByRole("heading", { name: "No run selected" }),
    ).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: "Start verification" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "temporarily unavailable",
      ),
    );
    expect(screen.queryByText(/Illustrative counts/)).toBeNull();
    expect(screen.queryByText("secret upstream detail")).toBeNull();
  });
  it("opens saved runs through an accessible dialog and returns focus on cancel", async () => {
    const user = userEvent.setup();
    render(<Dashboard />);
    await user.click(screen.getByRole("button", { name: "Live" }));
    const trigger = screen.getByRole("button", { name: "Open run" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Open saved run" });
    expect(within(dialog).getByLabelText("Run ID")).toBeTruthy();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
  it("keeps source selection visible while navigating", async () => {
    render(<Dashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Integrations" }));
    expect(screen.getByRole("heading", { name: "Integrations" })).toBeTruthy();
    expect(
      screen
        .getByRole("button", { name: "Fixture preview" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });
});
