import { notFound } from "next/navigation";
import { Kit } from "./Kit";

/** Dev-only showcase of every UI primitive. 404 in production builds. */
export default function KitPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <Kit />;
}
