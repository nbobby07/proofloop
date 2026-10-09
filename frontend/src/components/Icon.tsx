import {
  Activity,
  ChartNoAxesColumnIncreasing,
  History,
  Plug,
  ChevronRight,
  ArrowRight,
  Play,
  RotateCw,
  ShieldCheck,
  MoveUpRight,
  Code2,
  Check,
  FileText,
  Crosshair,
  Terminal,
  Info,
  Volume2,
  ExternalLink,
  Download,
  Fingerprint,
} from "lucide-react";
import type { LucideProps } from "lucide-react";

const icons = {
  arena: Activity,
  analytics: ChartNoAxesColumnIncreasing,
  history: History,
  integrations: Plug,
  chevron: ChevronRight,
  arrow: ArrowRight,
  play: Play,
  refresh: RotateCw,
  shield: ShieldCheck,
  attack: MoveUpRight,
  code: Code2,
  check: Check,
  file: FileText,
  target: Crosshair,
  terminal: Terminal,
  info: Info,
  volume: Volume2,
  external: ExternalLink,
  download: Download,
  fingerprint: Fingerprint,
};
export type IconName = keyof typeof icons;
export function Icon({ name, ...props }: LucideProps & { name: IconName }) {
  const Component = icons[name];
  return (
    <Component size={16} strokeWidth={1.6} aria-hidden="true" {...props} />
  );
}
export function ProofLoopMark() {
  return (
    <svg
      className="brand-mark"
      width="27"
      height="27"
      viewBox="0 0 28 28"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M14 2 24.4 8v12L14 26 3.6 20V8L14 2Z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="m9 10 5-3 5 3v5l-5 3m0 3-5-3v-5l5-3 5 3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}
