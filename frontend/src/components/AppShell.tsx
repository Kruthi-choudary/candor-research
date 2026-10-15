import { Link, NavLink, Outlet } from "react-router-dom";
import { Logo } from "./Logo";

export function AppShell() {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="dark">
        <header className="site-header container">
          <Link to="/" aria-label="Candor home">
            <Logo />
          </Link>
          <nav className="header-nav" aria-label="Main navigation">
            <NavLink to="/app" end>
              Research desk
            </NavLink>
            <NavLink to="/app/evaluation">Methodology & evaluation</NavLink>
          </nav>
          <span className="header-note">Independent intelligence</span>
        </header>
      </div>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="container footer-inner">
          <span>
            CANDOR <span aria-hidden="true"> / </span> Earnings-call
            intelligence
          </span>
          <span>Source first. Interpretation second.</span>
        </div>
      </footer>
    </>
  );
}
