import { db } from "./db";
const STALE_AFTER_MS=10*60*1000;
const runnable={OR:[{runAfter:null},{runAfter:{lte:new Date()}}]};
export async function enqueueJob(userId:string,projectId:string,type:string,payload:unknown={},runAfter?:Date){return db.job.create({data:{userId,projectId,type,payload,status:"QUEUED",runAfter}})}
export async function claimNextJob(){
 const staleBefore=new Date(Date.now()-STALE_AFTER_MS);
 const candidate=await db.job.findFirst({where:{AND:[{OR:[{status:"QUEUED"},{status:"RETRYING",startedAt:{lt:staleBefore}}]},runnable]},orderBy:{createdAt:"asc"}});
 if(!candidate)return null;
 const claimed=await db.job.updateMany({where:{AND:[{id:candidate.id},{OR:[{status:"QUEUED"},{status:"RETRYING",startedAt:{lt:staleBefore}}]},runnable]},data:{status:"RETRYING",startedAt:new Date(),attempts:{increment:1},finishedAt:null,error:null,runAfter:null}});
 return claimed.count?db.job.findUnique({where:{id:candidate.id}}):null;
}
export async function finishJob(id:string){return db.job.update({where:{id},data:{status:"READY",progress:1,finishedAt:new Date(),error:null}})}
export async function failJob(id:string,error:string){return db.job.update({where:{id},data:{status:"FAILED",error,finishedAt:new Date()}})}
