
import React from "react";
import ReactDOM from "react-dom/client";
import { BlueprintProvider } from "@blueprintjs/core";
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BlueprintProvider>
        <div>Hello World</div>
    </BlueprintProvider>
  </React.StrictMode>
);

