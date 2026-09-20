import { createFileRoute } from "@tanstack/react-router";
import { KeyInDesk } from "@/components/key-in-desk";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  return <KeyInDesk />;
}
