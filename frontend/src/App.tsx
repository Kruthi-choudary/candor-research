import { Routes, Route } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { CallReport } from "./pages/CallReport";
import { ClaimDetail } from "./pages/ClaimDetail";
import { Evaluation } from "./pages/Evaluation";
import { AppShell } from "./components/AppShell";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app" element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="evaluation" element={<Evaluation />} />
        <Route path="calls/:ticker/:quarter" element={<CallReport />} />
        <Route path="calls/:ticker/:quarter/claims/:index" element={<ClaimDetail />} />
      </Route>
    </Routes>
  );
}
