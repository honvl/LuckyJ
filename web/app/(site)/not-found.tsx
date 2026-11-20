// Shown when a guide or chapter address names nothing published (notFound() in the books pages).
import NotFoundBody from "@/components/NotFoundBody";
import { pageLang } from "@/lib/lang";

export default async function NotFound() {
  return <NotFoundBody lang={await pageLang()} />;
}
