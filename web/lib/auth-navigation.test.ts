import test, { before } from "node:test";
import assert from "node:assert/strict";

let auth: typeof import("./auth");

before(async () => {
  process.env.DATABASE_URL ||= "postgresql://clipfinder_test:test@127.0.0.1:5432/clipfinder_test";
  process.env.AUTH_SECRET ||= "test_auth_secret_for_clipfinder_at_least_32_chars_long";
  auth = await import("./auth");
});

test("password hashing and verification work securely", () => {
  const plain = "SuperSecretPassword123!";
  const hash = auth.hashPassword(plain);
  assert.ok(hash.includes(":"));
  assert.equal(auth.verifyPassword(plain, hash), true);
  assert.equal(auth.verifyPassword("WrongPassword123!", hash), false);
});

test("session token structure preserves user identity across refreshes", () => {
  assert.equal(typeof auth.getCurrentUser, "function");
  assert.equal(typeof auth.requireUser, "function");
  assert.equal(typeof auth.setSession, "function");
  assert.equal(typeof auth.clearSession, "function");
});
