import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dashboard } from "../pages/Dashboard";

async function preview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /change data source/ }));
  await user.click(
    within(screen.getByRole("group", { name: "Data source" })).getByRole(
      "button",
      { name: /Fixture preview/ },
    ),
  );
  await screen.findByRole("heading", {
    name: "Explore an example investigation.",
  });
}

describe("guided investigation workspace", () => {
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
  it("starts with the supported target and one primary action, without empty evidence panels", async () => {
    render(<Dashboard />);
    expect(
      screen.getByRole("heading", {
        name: "Find out whether your security fix actually works.",
      }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "LedgerLite Classic" })).toBeTruthy();
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: "Run security verification",
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(false),
    );
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Challenge this fix" }),
    ).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("keeps fixture outcomes illustrative and cannot execute from preview", async () => {
    const user = userEvent.setup();
    render(<Dashboard />);
    await preview(user);
    expect(screen.getByText(/Illustrative contract data/)).toBeTruthy();
    expect(
      screen.getByRole("heading", {
        name: "Explore an example investigation.",
      }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Run security verification" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Challenge this fix" }),
    ).toBeNull();
    await user.click(screen.getByRole("tab", { name: "Test results" }));
    expect(
      within(screen.getByRole("tabpanel")).getByText(/Illustrative counts/),
    ).toBeTruthy();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("supports keyboard evidence navigation and preserves the exact diff filter", async () => {
    const user = userEvent.setup();
    render(<Dashboard />);
    await preview(user);
    screen.getByRole("tab", { name: "Overview" }).focus();
    await user.keyboard("{ArrowRight}");
    const diff = screen.getByRole("tab", { name: "Code changes" });
    expect(diff.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(diff);
    await user.click(screen.getByRole("checkbox", { name: "Changes only" }));
    await user.click(screen.getByRole("tab", { name: "Test results" }));
    await user.click(diff);
    expect(
      (
        screen.getByRole("checkbox", {
          name: "Changes only",
        }) as HTMLInputElement
      ).checked,
    ).toBe(true);
    expect(screen.getByLabelText("Patch code changes").textContent).toContain(
      "+    if invoice.owner_id != user.id:",
    );
  });
  it("reports an actual request failure without falling back to illustrative success", async () => {
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
    await user.click(
      screen.getByRole("button", { name: "Run security verification" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "temporarily unavailable",
      ),
    );
    expect(screen.queryByText(/Illustrative counts/)).toBeNull();
    expect(screen.queryByText("secret upstream detail")).toBeNull();
  });
  it("puts opening a saved investigation in History", async () => {
    const user = userEvent.setup();
    render(<Dashboard />);
    await user.click(
      screen.getByRole("button", { name: "View previous runs" }),
    );
    expect(
      screen.getByRole("heading", { name: "Investigation history" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("Open a saved investigation")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open saved run" })).toBeTruthy();
  });
  it("presents the same fixture evidence and exits to the previous view with focus restored", async () => {
    const user = userEvent.setup();
    render(<Dashboard />);
    await preview(user);
    await user.click(screen.getByRole("tab", { name: "Code changes" }));
    const trigger = screen.getByRole("button", { name: "Presentation mode" });
    await user.click(trigger);
    expect(
      screen.queryByRole("navigation", { name: "Main navigation" }),
    ).toBeNull();
    expect(
      screen.getByRole("heading", {
        name: "Explore an example investigation.",
      }),
    ).toBeTruthy();
    expect(screen.getByText(/Illustrative contract data/)).toBeTruthy();
    await user.click(screen.getByRole("tab", { name: "Code changes" }));
    expect(screen.getByLabelText("Patch code changes")).toBeTruthy();
    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("navigation", { name: "Main navigation" }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("tab", { name: "Code changes" })
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Presentation mode" }),
    );
  });
});
