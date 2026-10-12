import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import SharedView from "./components/SharedView";
import "./index.css";

const sharedMatch = window.location.pathname.match(/^\/shared\/([A-Za-z0-9_-]+)\/?$/);
const sharedToken = sharedMatch ? sharedMatch[1] : null;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {sharedToken ? <SharedView token={sharedToken} /> : <App />}
  </React.StrictMode>
);
