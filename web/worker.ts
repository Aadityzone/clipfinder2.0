import {db} from "./lib/db";
import {claimNextJob,finishJob,failJob} from "./lib/jobs";
const sleep=(ms:number)=>new Promise(r=>setTimeout(r,ms));
async function tick(){
 const job=await claimNextJob();if(!job)return;
 try{
  if(job.type==="PROJECT_READY"){await finishJob(job.id);return}
  if(job.type==="INGEST"){await db.job.update({where:{id:job.id},data:{status:"FAILED",error:"Remote ingestion worker is being connected to the Python downloader."}});return}
  await failJob(job.id,"Unknown job type: "+job.type);
 }catch(e){await failJob(job.id,e instanceof Error?e.message:String(e))}
}
async function main(){console.log("[worker] started");while(true){await tick();await sleep(1000)}}
main().catch(e=>{console.error(e);process.exit(1)})