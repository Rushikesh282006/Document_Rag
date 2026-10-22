import { createFileRoute } from "@tanstack/react-router";
import { AuthForm } from "@/components/AuthForm";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Groundwork RAG" },
      { name: "description", content: "Sign in to query your tenant's knowledge base." },
      { property: "og:title", content: "Sign in — Groundwork RAG" },
      { property: "og:description", content: "Sign in to query your tenant's knowledge base." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => <AuthForm kind="login" />,
});
