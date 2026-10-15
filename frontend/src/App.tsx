import { Routes, Route, useParams, Link } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { CallReport } from "./pages/CallReport";
import { ClaimDetail } from "./pages/ClaimDetail";
import { Evaluation } from "./pages/Evaluation";
import { AppShell } from "./components/AppShell";

function CallRoute({ evidence = false }: { evidence?: boolean }) {
  const { ticker, quarter } = useParams();
  return evidence ? (
    <ClaimDetail key={`${ticker}/${quarter}`} />
  ) : (
    <CallReport key={`${ticker}/${quarter}`} />
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app" element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="evaluation" element={<Evaluation />} />
        <Route path="calls/:ticker/:quarter" element={<CallRoute />} />
        <Route
          path="calls/:ticker/:quarter/claims/:index"
          element={<CallRoute evidence />}
        />
        <Route
          path="*"
          element={
            <div className="container page state-panel">
              <h1 className="page-title">This page isn’t in the library.</h1>
              <Link className="btn mt-6" to="/app">
                Back to research desk
              </Link>
            </div>
          }
        />
      </Route>
      <Route path="*" element={<AppShell />}>
        <Route
          path="*"
          element={
            <div className="container page state-panel">
              <h1 className="page-title">This page isn’t in the library.</h1>
              <Link className="btn mt-6" to="/app">
                Back to research desk
              </Link>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
