import { NextRequest } from "next/server";
import { db } from "../../../../lib/db";
import { hashPassword, setSession } from "../../../../lib/auth";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(req: NextRequest) {
  const parsed = await req.json().catch(() => null);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return Response.json({ error: "Send a valid JSON object." }, { status: 400 });
  }

  const body = parsed as Record<string, unknown>;
  const email = String(body.email ?? "").trim().toLowerCase();
  const password = String(body.password ?? "");
  const rawName = String(body.name ?? "").trim();
  const name = rawName ? rawName.slice(0, 80) : null;

  if (
    email.length > 254 ||
    !EMAIL_PATTERN.test(email) ||
    password.length < 8 ||
    password.length > 1024
  ) {
    return Response.json(
      { error: "Enter a valid email and a password between 8 and 1024 characters." },
      { status: 400 },
    );
  }

  const existing = await db.user.findUnique({ where: { email }, select: { id: true } });
  if (existing) {
    return Response.json({ error: "An account with that email already exists." }, { status: 409 });
  }

  try {
    const user = await db.user.create({
      data: {
        email,
        name,
        passwordHash: hashPassword(password),
        subscription: { create: {} },
        usage: { create: {} },
      },
      select: { id: true, email: true, name: true },
    });
    await setSession(user.id);
    return Response.json({ user }, { status: 201 });
  } catch (error) {
    // A concurrent signup can pass the pre-check; the unique index remains the
    // source of truth and should produce the same response as the pre-check.
    if (
      error !== null &&
      typeof error === "object" &&
      "code" in error &&
      error.code === "P2002"
    ) {
      return Response.json({ error: "An account with that email already exists." }, { status: 409 });
    }
    throw error;
  }
}
