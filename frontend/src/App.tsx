import { MotionConfig } from "motion/react";
import { Dashboard } from "./pages/Dashboard";
import { motionTokens } from "./components/motion";

export default function App() {
  return (
    <MotionConfig
      reducedMotion="user"
      transition={{ duration: motionTokens.panel, ease: motionTokens.ease }}
    >
      <Dashboard />
    </MotionConfig>
  );
}
