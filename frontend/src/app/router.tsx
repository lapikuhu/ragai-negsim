import { createBrowserRouter } from "react-router-dom";
import { App } from "@/App";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/app/ProtectedRoute";
import { LoginPage } from "@/features/auth/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { SessionsPage } from "@/pages/SessionsPage";
import { SessionDetailPage } from "@/pages/SessionDetailPage";
import { SimulationsPage } from "@/pages/SimulationsPage";
import { SimulationCockpitPage } from "@/pages/SimulationCockpitPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { DocumentDetailPage } from "@/pages/DocumentDetailPage";
import { CorporaPage } from "@/pages/CorporaPage";
import { CorpusDetailPage } from "@/pages/CorpusDetailPage";
import { ScenariosPage } from "@/pages/ScenariosPage";
import { PersonasPage } from "@/pages/PersonasPage";
import { PromptsPage } from "@/pages/PromptsPage";
import { ChunkingProfilesPage } from "@/pages/ChunkingProfilesPage";
import { RagProfilesPage } from "@/pages/RagProfilesPage";
import { EvaluationsPage } from "@/pages/EvaluationsPage";
import { EvaluationReviewPage } from "@/pages/EvaluationReviewPage";
import { ModelsPage } from "@/pages/ModelsPage";
import { IndexingPage } from "@/pages/IndexingPage";
import { UsersPage } from "@/pages/UsersPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { VectorStoresPage } from "@/pages/VectorStoresPage";
import { KnowledgeGraphsPage } from "@/pages/KnowledgeGraphsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { path: "/login", element: <LoginPage /> },
      {
        element: <ProtectedRoute />,
        children: [
          {
            element: <AppShell />,
            children: [
              { index: true, element: <DashboardPage /> },
              { path: "simulations", element: <SimulationsPage /> },
              { path: "simulations/:simulationId", element: <SimulationCockpitPage /> },
              { path: "documents", element: <DocumentsPage /> },
              { path: "documents/:documentId", element: <DocumentDetailPage /> },
              { path: "corpora", element: <CorporaPage /> },
              { path: "corpora/:corpusId", element: <CorpusDetailPage /> },
              { path: "settings", element: <SettingsPage /> }
            ]
          }
        ]
      },
      {
        element: <ProtectedRoute roles={["teacher", "admin"]} />,
        children: [
          {
            element: <AppShell />,
            children: [
              { path: "scenarios", element: <ScenariosPage /> },
              { path: "personas", element: <PersonasPage /> },
              { path: "evaluations", element: <EvaluationsPage /> },
              { path: "evaluations/:simulationId/review", element: <EvaluationReviewPage /> }
            ]
          }
        ]
      },
      {
        element: <ProtectedRoute roles={["admin"]} />,
        children: [
          {
            element: <AppShell />,
            children: [
              { path: "sessions", element: <SessionsPage /> },
              { path: "sessions/:sessionId", element: <SessionDetailPage /> },
              { path: "prompts", element: <PromptsPage /> },
              { path: "chunking-profiles", element: <ChunkingProfilesPage /> },
              { path: "rag-profiles", element: <RagProfilesPage /> },
              { path: "knowledge-graphs", element: <KnowledgeGraphsPage /> },
              { path: "indexing", element: <IndexingPage /> },
              { path: "vector-stores", element: <VectorStoresPage /> },
              { path: "models", element: <ModelsPage /> },
              { path: "users", element: <UsersPage /> }
            ]
          }
        ]
      }
    ]
  }
]);
