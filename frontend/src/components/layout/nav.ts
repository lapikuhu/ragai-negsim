export type NavItem = {
  label: string;
  to: string;
  description: string;
  roles?: string[];
  disabled?: boolean;
};

export const navigationItems: NavItem[] = [
  { label: "Dashboard", to: "/", description: "Overview and quick actions" },
  { label: "Simulations", to: "/simulations", description: "Negotiation cockpit and history" },
  { label: "User Sessions", to: "/sessions", description: "Login and session records", roles: ["admin"] },
  { label: "Documents", to: "/documents", description: "Raw document upload and inspection" },
  { label: "Corpora", to: "/corpora", description: "Corpus, chunking, index, and RAG controls" },
  { label: "Scenarios", to: "/scenarios", description: "Scenario catalog", roles: ["teacher", "admin"] },
  { label: "Personas", to: "/personas", description: "Counterpart personas", roles: ["teacher", "admin"] },
  { label: "Prompts", to: "/prompts", description: "Prompt registry", roles: ["admin"] },
  { label: "Chunking Profiles", to: "/chunking-profiles", description: "Reusable ingestion profile management", roles: ["admin"] },
  { label: "Indexing", to: "/indexing", description: "Run and monitor full corpus indexing jobs", roles: ["admin"] },
  { label: "Evaluations", to: "/evaluations", description: "Review outputs and feedback" },
  { label: "Models", to: "/models", description: "Embedding models and vector stores", roles: ["admin"] },
  { label: "Users", to: "/users", description: "User administration", roles: ["admin"] },
  { label: "Settings", to: "/settings", description: "Read-only capability map" }
];
