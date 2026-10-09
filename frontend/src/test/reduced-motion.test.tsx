import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import App from "../App";
import { saveSelection } from "../features/execution/session";

it("renders the evidence immediately and preserves presentation controls with a reduced-motion preference", async () => {
  const media = vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true,
  }));
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ status: "ok", service: "proofloop" })),
      ),
  );
  saveSelection("source", "fixture");
  const user = userEvent.setup();
  render(<App />);
  const title = await screen.findByRole("heading", {
    name: "Explore an example investigation.",
  });
  expect(title.parentElement?.style.opacity).toBe("1");
  await user.click(screen.getByRole("button", { name: "Presentation mode" }));
  await user.click(screen.getByRole("tab", { name: "Code changes" }));
  expect(screen.getByLabelText("Patch code changes")).toBeTruthy();
  await user.keyboard("{Escape}");
  expect(
    screen.getByRole("navigation", { name: "Main navigation" }),
  ).toBeTruthy();
  media.mockRestore();
});
