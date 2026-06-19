import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { router } from "@/app/router";
import { queryClient } from "@/app/queryClient";
import { AuthProvider } from "@/app/AuthProvider";
import { LlmModelCatalogPrefetch } from "@/features/llmModels/LlmModelCatalogPrefetch";
import "@/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <LlmModelCatalogPrefetch />
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
