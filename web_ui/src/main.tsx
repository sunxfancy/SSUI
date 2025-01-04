import React from "react";
import ReactDOM from "react-dom/client";
import { BlueprintProvider } from "@blueprintjs/core";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BlueprintProvider>
      <App />
    </BlueprintProvider>
  </React.StrictMode>
);
