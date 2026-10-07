import {db} from "./lib/db";
import {claimNextJob,finishJob,failJob} from "./lib/jobs";
const sleep=(ms:number)=>new Promise(r=>setTimeout(r,ms));
const AI=process.env.AI_SERVICE_URL||"http://127.0.0.1:8000";
async function ai(path:string,body:unknown){const r=await fetch(AI+path,{method:"POST",headers:{"content-type":"application/json",...(process.env.AI_SERVICE_SECRET?{"x-ai-secret":process.env.AI_SERVICE_SECRET}:{})},body:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()}
async function tick(){
 const j=await claimNextJob();if(!j)return;
 try{
  if(j.type==="PROJECT_READY"){await finishJob(j.id);return}
  if(j.type==="INGEST"){
   const p=(j.payload||{}) as {sourceUrl?:string};if(!p.sourceUrl)throw new Error("INGEST job has no sourceUrl");
   const root=process.env.MEDIA_STORAGE_ROOT||"../storage";
   const r=await ai("/v1/ingest",{url:p.sourceUrl,output_dir:root+"/sources"});
   const source=await db.source.findFirst({where:{id:(await db.project.findUniqueOrThrow({where:{id:j.projectId!}})).sourceId!}});
   if(!source)throw new Error("Project source missing");
   const asset=await db.mediaAsset.create({data:{sourceId:source.id,storageKey:r.media_path,mimeType:"video/mp4",durationS:r.metadata.duration,width:r.metadata.width,height:r.metadata.height,fps:r.metadata.fps,codec:r.metadata.codec,hasAudio:r.metadata.hasAudio}});
   await db.job.update({where:{id:j.id},data:{status:"TRANSCRIBING",progress:.5,payload:{...p,mediaAssetId:asset.id,mediaPath:r.media_path}}});
   await db.job.create({data:{userId:j.userId,projectId:j.projectId,type:"TRANSCRIBE",status:"QUEUED",payload:{mediaAssetId:asset.id,mediaPath:r.media_path}}});return
  }
  if(j.type==="TRANSCRIBE"){
   const p=(j.payload||{}) as {mediaAssetId:string;mediaPath:string};const r=await ai("/v1/transcribe",{media_path:p.mediaPath});
   const t=await db.transcript.create({data:{mediaAssetId:p.mediaAssetId,language:r.language,text:r.text,metadata:{duration:r.duration},segments:{create:r.segments.map((s:any)=>({startS:s.start,endS:s.end,text:s.text,confidence:s.confidence,words:{create:s.words.map((w:any)=>({startS:w.start,endS:w.end,word:w.word,confidence:w.confidence}))}}))}}});
   await db.job.update({where:{id:j.id},data:{status:"ANALYZING",progress:.9,payload:{...p,transcriptId:t.id}}});
   await db.job.create({data:{userId:j.userId,projectId:j.projectId,type:"ANALYZE",status:"QUEUED",payload:{transcriptId:t.id}}});return
  }
  if(j.type==="ANALYZE"){throw new Error("Candidate analysis worker is the next pipeline stage")}
  throw new Error("Unknown job type: "+j.type)
 }catch(e){await failJob(j.id,e instanceof Error?e.message:String(e))}
}
async function main(){console.log("[worker] started");while(true){await tick();await sleep(1000)}}main().catch(e=>{console.error(e);process.exit(1)});
