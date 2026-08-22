import React from "react";
import ReactDOM from "react-dom/client";
import { BlueprintProvider } from "@blueprintjs/core";
import App from "./App";
import { ConfigProvider } from "./config";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BlueprintProvider>
      <ConfigProvider>
        <App />
      </ConfigProvider>
    </BlueprintProvider>
  </React.StrictMode>
);
