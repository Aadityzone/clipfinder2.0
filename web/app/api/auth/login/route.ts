import { NextRequest } from "next/server";
import { db } from "../../../../lib/db";
import { setSession, verifyPassword } from "../../../../lib/auth";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(req: NextRequest) {
  const parsed = await req.json().catch(() => null);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return Response.json({ error: "Invalid email or password." }, { status: 401 });
  }

  const body = parsed as Record<string, unknown>;
  const email = String(body.email ?? "").trim().toLowerCase();
  const password = String(body.password ?? "");
  if (email.length > 254 || !EMAIL_PATTERN.test(email) || password.length < 8 || password.length > 1024) {
    return Response.json({ error: "Invalid email or password." }, { status: 401 });
  }

  try {
    const user = await db.user.findUnique({ where: { email } });
    if (!user) return Response.json({ error: "Invalid email or password." }, { status: 401 });

    if (user.lockedUntil && user.lockedUntil.getTime() > Date.now()) {
      return Response.json({ error: "Too many failed attempts. Try again later." }, { status: 429 });
    }

    if (!verifyPassword(password, user.passwordHash)) {
      const attempts = user.failedLoginCount + 1;
      await db.user.update({
        where: { id: user.id },
        data: {
          failedLoginCount: attempts,
          lockedUntil: attempts >= 8 ? new Date(Date.now() + 15 * 60 * 1000) : null,
        },
      });
      return Response.json({ error: "Invalid email or password." }, { status: 401 });
    }

    await db.user.update({
      where: { id: user.id },
      data: { failedLoginCount: 0, lockedUntil: null },
    });
    await setSession(user.id);
    return Response.json({ user: { id: user.id, email: user.email, name: user.name } });
  } catch (error) {
    console.error("Login failed:", error);
    return Response.json(
      { error: "Sign-in is temporarily unavailable. Check the database connection and server logs, then try again." },
      { status: 500 },
    );
  }
}
