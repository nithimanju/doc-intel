import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./styles/custom.scss";
import "./App.css";

// Bootstrap 5.3's native color-mode system: follow the OS preference via
// data-bs-theme on <html>, per https://getbootstrap.com/docs/5.3/customize/color-modes/
function syncBootstrapTheme() {
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-bs-theme", dark ? "dark" : "light");
}
syncBootstrapTheme();
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncBootstrapTheme);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
