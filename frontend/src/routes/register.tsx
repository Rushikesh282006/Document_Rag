import { createFileRoute } from "@tanstack/react-router";
import { AuthForm } from "@/components/AuthForm";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — Groundwork RAG" },
      { name: "description", content: "Create a tenant account and start building your knowledge base." },
      { property: "og:title", content: "Create account — Groundwork RAG" },
      { property: "og:description", content: "Create a tenant account and start building your knowledge base." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => <AuthForm kind="register" />,
});
