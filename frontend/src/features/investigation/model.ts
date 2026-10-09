import type { RunResponse, RunStatus, SecurityEvent } from "../../types";
import { terminal } from "../execution/lifecycle";

export type EvidenceView = "overview" | "diff" | "results" | "audit" | "report";
export const phases = [
  "Find the problem",
  "Generate and test a fix",
  "Challenge and verify",
];
const phaseMap: Partial<Record<RunStatus, number>> = {
  pending: 0,
  discovering: 0,
  reproducing: 0,
  generating_patch: 1,
  applying_patch: 1,
  verifying: 1,
  retrying: 1,
  challenging: 2,
  verified: 2,
};
export function currentPhase(run: RunResponse, events: SecurityEvent[]) {
  if (phaseMap[run.status] !== undefined) return phaseMap[run.status]!;
  const previous = [...events]
    .reverse()
    .find((event) => !terminal(event.stage));
  return previous ? (phaseMap[previous.stage] ?? 0) : 0;
}
export function checkCounts(run: RunResponse) {
  const result = run.verification;
  if (!result) return null;
  return {
    passed:
      result.security_passed +
      result.functional_passed +
      result.adversarial_passed,
    total:
      result.security_total +
      result.functional_total +
      result.adversarial_total,
  };
}
export function isInvoiceFinding(run: RunResponse) {
  return (
    run.target === "LedgerLite" &&
    (run.finding?.id === "BOLA-001" ||
      /invoice-missing-ownership|Broken Object Level Authorization/i.test(
        run.finding?.title ?? "",
      ))
  );
}
export function issueDescription(run: RunResponse) {
  if (run.baseline?.reproduced)
    return isInvoiceFinding(run)
      ? "One account could access another account’s invoice."
      : "The reported vulnerability was independently reproduced.";
  if (run.baseline) return "The reported vulnerability was not reproduced.";
  return run.finding
    ? "A potential weakness was found. Reproduction is not yet recorded."
    : "No vulnerability has been confirmed yet.";
}
export function attemptHistory(run: RunResponse, events: SecurityEvent[]) {
  const numbers = new Set<number>();
  if (run.patch) numbers.add(run.patch.attempt);
  for (const event of events) {
    const attempt = event.metadata?.attempt;
    if (
      typeof attempt === "number" &&
      Number.isInteger(attempt) &&
      attempt > 0 &&
      attempt <= 10
    )
      numbers.add(attempt);
  }
  return [...numbers]
    .sort((a, b) => a - b)
    .map((attempt) => {
      const rounds = events.filter(
        (event) =>
          event.event_type === "test_completed" &&
          event.metadata?.attempt === attempt,
      );
      const last = rounds[rounds.length - 1];
      const failed =
        last?.source === "execution" &&
        last.metadata?.executed === true &&
        last.metadata?.outcome === "fail";
      const passed =
        last?.source === "execution" &&
        last.metadata?.executed === true &&
        last.metadata?.outcome === "pass";
      const current = attempt === run.patch?.attempt;
      const proposed =
        current ||
        events.some(
          (event) =>
            event.event_type === "patch_proposed" &&
            event.metadata?.attempt === attempt,
        );
      const label =
        run.source === "fixture"
          ? "Illustrative"
          : current && run.status === "verified"
            ? "Verified"
            : current && run.status === "challenging"
              ? "Under challenge"
              : failed
                ? "Rejected"
                : current && run.status === "rejected"
                  ? "Rejected"
                  : current &&
                      (run.status === "inconclusive" || run.status === "error")
                    ? "Incomplete"
                    : passed
                      ? "Checks passed"
                      : proposed
                        ? "Proposed"
                        : "Evidence unavailable";
      const tone =
        label === "Verified" || label === "Checks passed"
          ? "pass"
          : label === "Rejected"
            ? "fail"
            : "pending";
      return { attempt, label, tone, rounds };
    });
}
export function resultCopy(run: RunResponse, events: SecurityEvent[]) {
  if (run.source === "fixture")
    return {
      label: "Fixture preview",
      title: "Explore an example investigation.",
      description:
        "This is illustrative contract data. No attacks or tests in this preview were executed.",
      tone: "preview",
    };
  if (
    run.target === "LedgerLite Workspace" &&
    run.status === "inconclusive" &&
    events.some(
      (e) =>
        e.event_type === "run_completed" &&
        e.message.includes("no_reproducible_finding"),
    )
  )
    return {
      label: "Audit complete",
      title: "No reproducible vulnerability found.",
      description:
        "The executed checks did not establish a security failure. Review the scanner findings, generated challenges and execution evidence below. This is not a claim of universal security.",
      tone: "pending",
    };
  const counts = checkCounts(run);
  const priorFailure = events.some(
    (event) =>
      event.source === "execution" &&
      event.event_type === "test_completed" &&
      event.metadata?.executed === true &&
      event.metadata?.outcome === "fail" &&
      typeof event.metadata.attempt === "number" &&
      event.metadata.attempt < (run.patch?.attempt ?? 0),
  );
  if (run.status === "verified")
    return {
      label: "Verified",
      title:
        counts && counts.total > 0 && counts.passed === counts.total
          ? `Patch verified against ${counts.total} executed checks.`
          : "Patch verified by independent testing.",
      description: priorFailure
        ? "An earlier proposal failed independent testing. The revised patch passed the required security, functional and adversarial checks."
        : "The independent verifier accepted this patch against the required security, functional and adversarial checks.",
      tone: "pass",
    };
  if (run.status === "rejected")
    return {
      label: "Rejected",
      title: "This fix did not pass verification.",
      description:
        "Required checks failed. The unsuccessful attempts remain in the record so you can inspect what happened.",
      tone: "fail",
    };
  if (run.status === "inconclusive")
    return {
      label: "Inconclusive",
      title: "There isn’t enough evidence for a verdict.",
      description:
        "Required verification is incomplete or unavailable. Recorded passing counts do not establish a successful result.",
      tone: "incomplete",
    };
  return {
    label: "Execution error",
    title: "The investigation could not finish.",
    description:
      "An execution or provider error interrupted this run. Review the recorded events before starting another investigation.",
    tone: "fail",
  };
}
export const activityCopy: Record<
  Exclude<RunStatus, "verified" | "rejected" | "inconclusive" | "error">,
  { title: string; description: string }
> = {
  pending: {
    title: "Your investigation is queued.",
    description:
      "ProofLoop is waiting to begin the supported LedgerLite verification.",
  },
  discovering: {
    title: "Looking for an authorization weakness.",
    description:
      "ProofLoop is inspecting LedgerLite for a security issue that can be reproduced.",
  },
  reproducing: {
    title: "Can one account reach another account’s invoice?",
    description:
      "The independent runner is checking the original application. A finding alone is not proof.",
  },
  generating_patch: {
    title: "Preparing a proposed fix.",
    description:
      "The defender is generating a patch. Independent tests will decide whether it works.",
  },
  applying_patch: {
    title: "Preparing the patch for testing.",
    description:
      "The proposal is being applied in an isolated workspace before verification.",
  },
  verifying: {
    title: "Testing the proposed fix independently.",
    description:
      "Security, functional and adversarial checks must complete before a verdict can be recorded.",
  },
  retrying: {
    title: "The last attempt needs another approach.",
    description:
      "The unsuccessful attempt is preserved. ProofLoop is preparing another proposal within the run’s attempt budget.",
  },
  challenging: {
    title: "Putting the fix through fresh challenges.",
    description:
      "The previous verdict is invalidated. A new result will appear only after independent verification completes.",
  },
};
