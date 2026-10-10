import dotenv from "dotenv";
import { defineConfig, env } from "prisma/config";

// Prisma CLI runs from the repository root, while the web app keeps its
// private development environment in web/.env.local. Load that file explicitly
// so schema commands use the same DATABASE_URL as the application.
dotenv.config({ path: "web/.env.local" });
dotenv.config();

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: { path: "prisma/migrations" },
  datasource: { url: env("DATABASE_URL") },
});
