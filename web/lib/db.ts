import { PrismaClient } from "../generated/prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };
function createPrisma() {
  const url=process.env.DATABASE_URL;
  if(!url) throw new Error("DATABASE_URL is not configured");
  return new PrismaClient({adapter:new PrismaPg({connectionString:url})});
}
export const db=globalForPrisma.prisma ?? createPrisma();
if(process.env.NODE_ENV!=="production") globalForPrisma.prisma=db;