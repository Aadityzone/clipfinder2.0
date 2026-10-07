import { createHmac, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import { db } from "./db";
const COOKIE="cf_session";
function secret(){const s=process.env.AUTH_SECRET;if(!s) throw new Error("AUTH_SECRET is not configured");return s}
function enc(v:string){return Buffer.from(v).toString("base64url")}
function sign(p:string){return createHmac("sha256",secret()).update(p).digest("base64url")}
function makeToken(id:string){const p=enc(JSON.stringify({sub:id,exp:Date.now()+2592000000}));return p+"."+sign(p)}
function verify(t:string){const [p,s]=t.split(".");if(!p||!s)return null;const a=Buffer.from(s),b=Buffer.from(sign(p));if(a.length!==b.length||!timingSafeEqual(a,b))return null;const x=JSON.parse(Buffer.from(p,"base64url").toString());return x.exp>Date.now()?x.sub:null}
export function hashPassword(p:string){const salt=randomBytes(16).toString("hex");return salt+":"+scryptSync(p,salt,64).toString("hex")}
export function verifyPassword(p:string,stored:string){const [salt,hash]=stored.split(":");if(!salt||!hash)return false;return timingSafeEqual(scryptSync(p,salt,64),Buffer.from(hash,"hex"))}
export async function setSession(id:string){(await cookies()).set(COOKIE,makeToken(id),{httpOnly:true,sameSite:"lax",secure:process.env.NODE_ENV==="production",path:"/",maxAge:2592000})}
export async function clearSession(){(await cookies()).delete(COOKIE)}
export async function getCurrentUser(){const t=(await cookies()).get(COOKIE)?.value;if(!t)return null;const id=verify(t);return id?db.user.findUnique({where:{id}}):null}
export async function requireUser(){const u=await getCurrentUser();if(!u)throw new Error("UNAUTHENTICATED");return u}