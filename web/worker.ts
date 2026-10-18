import {db} from "./lib/db";import {loadCreatorFeedbackProfile} from "./lib/creator-feedback";import {claimNextJob,finishJob,failJob,assertJobNotCancelled,completeJobAndEnqueue} from "./lib/jobs";import {analysisEntitlement,nextRangeChunk,toMediaLocalSegments,toSourceTimestamps,validateAnalysisRange} from "./lib/analysis-range";import path from "node:path";import{ensureLocalStorage,putFile}from"./lib/storage";import{downloadGoogleDrive}from"./lib/sources/google-drive";import{publishYouTube}from"./lib/publish/youtube";import{publishTikTok,tiktokPublishStatus}from"./lib/publish/tiktok";import{STAGE_TIMEOUT_MS,MAX_SOURCE_CHUNK_SECONDS,resolveAiServiceUrl,AiServiceError,isPermanentFailure}from"./lib/worker-config";
const sleep=(n:number)=>new Promise(r=>setTimeout(r,n));const AI=resolveAiServiceUrl();
function log(level: "info" | "warn" | "error", message: string, data?: Record<string, unknown>) {
  const entry = { ts: new Date().toISOString(), level, msg: message, ...data };
  console[level === "error" ? "error" : "log"](JSON.stringify(entry));
}
async function finishAnalysisAndQueueNext(j:any,p:any,mediaAssetId:string){
 const range=p.sourceRange;const offset=Number(p.mediaOffsetSeconds||0);const cursor=Number(p.rangeCursorSeconds??(Number(range?.startSeconds||0)-offset));
 if(p.continueAfterRange&&range&&cursor<Number(range.endSeconds)-offset){
  return completeJobAndEnqueue(j.id,{userId:j.userId,projectId:j.projectId,type:"TRANSCRIBE",payload:{mediaAssetId,sourceRange:range,sourceDurationS:p.sourceDurationS,mediaOffsetSeconds:offset,rangeLimitedDownload:Boolean(p.rangeLimitedDownload),rangeConfirmed:Boolean(p.rangeConfirmed),rangeCursorSeconds:cursor,continueAfterRange:true}});
 }
 return finishJob(j.id);
}
async function setJobProgress(id:string,progress:number,status?:"DOWNLOADING"|"INGESTING"|"TRANSCRIBING"|"ANALYZING"|"RENDERING"){await db.job.updateMany({where:{id,status:{notIn:["CANCELLED","READY","FAILED"]}},data:{progress,...(status?{status}:{})}})}
async function ai(pathname:string,body:unknown,timeoutMs?:number){
  const timeout = timeoutMs ?? STAGE_TIMEOUT_MS.DEFAULT;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const started = Date.now();
  log("info", "ai_call_start", { endpoint: pathname, timeoutMs: timeout });
  try {
    const r = await fetch(AI + pathname, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(process.env.AI_SERVICE_SECRET ? { "x-ai-secret": process.env.AI_SERVICE_SECRET } : {}),
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!r.ok) {
      // Keep the status so the failure can be classified as transient or
      // permanent, and clamp the body so a large HTML error page is not stored
      // wholesale as the job error.
      const detail = (await r.text().catch(() => "")).slice(0, 500);
      throw new AiServiceError(pathname, r.status, detail);
    }
    const result = await r.json();
    log("info", "ai_call_done", { endpoint: pathname, durationMs: Date.now() - started });
    return result;
  } catch (e: any) {
    const durationMs = Date.now() - started;
    if (e?.name === "AbortError" || controller.signal.aborted) {
      throw new Error(`AI service call to ${pathname} timed out after ${Math.round(timeout / 1000)}s (elapsed ${Math.round(durationMs / 1000)}s)`);
    }
    log("error", "ai_call_failed", { endpoint: pathname, durationMs, error: e?.message });
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
async function queueDuePosts(){const due=await db.scheduledPost.findMany({where:{status:"SCHEDULED",scheduledFor:{lte:new Date()}},take:10});for(const post of due){const changed=await db.scheduledPost.updateMany({where:{id:post.id,status:"SCHEDULED"},data:{status:"PUBLISHING",error:null}});if(changed.count)await db.job.create({data:{userId:post.userId,type:"PUBLISH",projectId:post.clipId?((await db.clip.findUnique({where:{id:post.clipId},select:{projectId:true}}))?.projectId):undefined,payload:{scheduledPostId:post.id}}})}}
async function tick(){await queueDuePosts();const j=await claimNextJob();if(!j)return;log("info","job_claimed",{jobId:j.id,type:j.type,projectId:j.projectId});const heartbeat=setInterval(()=>{void db.job.updateMany({where:{id:j.id,status:{in:["RETRYING","DOWNLOADING","INGESTING","TRANSCRIBING","ANALYZING","EDITING","RENDERING"]}},data:{startedAt:new Date()}}).catch(error=>console.error("[worker] heartbeat failed",error));},30_000);heartbeat.unref?.();try{await setJobProgress(j.id,.02);
 if(j.type==="PROJECT_READY"){await assertJobNotCancelled(j.id);await finishJob(j.id);log("info","job_finished",{jobId:j.id,type:j.type});return}
 if(j.type==="INGEST"){
  await setJobProgress(j.id,.05,"INGESTING");
  const p=j.payload as any;
  if(!p?.sourceUrl)throw new Error("Missing sourceUrl");
  const project=await db.project.findUniqueOrThrow({where:{id:j.projectId!}});
  const source=await db.source.findUniqueOrThrow({where:{id:project.sourceId!}});
  const storageRoot=path.resolve(process.env.MEDIA_STORAGE_ROOT||"../storage");
  let asset=await db.mediaAsset.findFirst({where:{sourceId:source.id},orderBy:{createdAt:"desc"}});
  let sourceDurationS=Number(p.sourceDurationS||0);
  if(p.sourceRange&&p.rangeConfirmed){
    const [subscription,metadata]=await Promise.all([
      db.subscription.findUnique({where:{userId:j.userId},select:{plan:true,status:true}}),
      source.type==="GOOGLE_DRIVE"?Promise.resolve(null):ai("/v1/source-metadata",{url:p.sourceUrl},STAGE_TIMEOUT_MS.METADATA),
    ]);
    sourceDurationS=Number(metadata?.duration||sourceDurationS);
    const checked=validateAnalysisRange({startSeconds:p.sourceRange.startSeconds,endSeconds:p.sourceRange.endSeconds,sourceDurationSeconds:sourceDurationS,entitlement:analysisEntitlement(subscription)});
    p.sourceRange={startSeconds:checked.startMs/1000,endSeconds:checked.endMs/1000};
  }
  if(!asset){
    let mediaPath:string;
    let metadata:any;
    let mimeType="video/mp4";
    if(source.type==="GOOGLE_DRIVE"){
      await setJobProgress(j.id,.12,"DOWNLOADING");
      const match=p.sourceUrl.match(/(?:\/file\/d\/|[?&]id=)([A-Za-z0-9_-]+)/);
      if(!match)throw new Error("Invalid Google Drive file URL");
      const key="sources/google-drive/"+j.userId+"/"+match[1]+".media";
      mediaPath=path.resolve(storageRoot,key);
      const drive=await downloadGoogleDrive(j.userId,match[1],mediaPath);
      mimeType=String(drive.mimeType||mimeType);
      metadata=await ai("/v1/probe",{media_path:mediaPath},STAGE_TIMEOUT_MS.PROBE);
    }else{
      await setJobProgress(j.id,.12,"DOWNLOADING");
      const result=await ai("/v1/ingest",{url:p.sourceUrl,output_dir:path.join(storageRoot,"sources"),...(p.sourceRange&&p.rangeLimitedDownload?{start_seconds:p.sourceRange.startSeconds,end_seconds:p.sourceRange.endSeconds}:{})},STAGE_TIMEOUT_MS.INGEST);
      mediaPath=result.media_path;
      metadata=result.metadata;
      if(!sourceDurationS)sourceDurationS=Number(metadata.sourceDuration||metadata.duration||0);
    }
    await assertJobNotCancelled(j.id);
    const relative=path.relative(storageRoot,mediaPath);
    if(relative===".."||relative.startsWith(".."+path.sep)||path.isAbsolute(relative)){
      throw new Error("AI media path is outside shared MEDIA_STORAGE_ROOT. Configure the web worker and AI service to use the same mounted media directory.");
    }
    const storageKey=relative.replaceAll("\\","/");
    await putFile(storageKey,mediaPath,mimeType);
    asset=await db.mediaAsset.create({data:{
      sourceId:source.id,storageKey,mimeType,durationS:metadata.duration,
      width:metadata.width,height:metadata.height,fps:metadata.fps,
      codec:metadata.codec,hasAudio:metadata.hasAudio,
    }});
  }
  await assertJobNotCancelled(j.id);
  if(!Number.isFinite(sourceDurationS)||sourceDurationS<=0)sourceDurationS=Number(asset.durationS||0);
  if(!Number.isFinite(sourceDurationS)||sourceDurationS<=0)throw new Error("Source media has no valid duration.");
  let sourceRange=p.sourceRange||{startSeconds:0,endSeconds:sourceDurationS};
  const isRangeLimitedDownload=Boolean(p.rangeLimitedDownload&&p.sourceRange&&source.type!=="GOOGLE_DRIVE");
  const mediaOffsetSeconds=isRangeLimitedDownload?Number(sourceRange.startSeconds):0;
  const selectedDuration=Number(sourceRange.endSeconds)-Number(sourceRange.startSeconds);
  const mediaDuration=Number(asset.durationS||0);
  if(!Number.isFinite(selectedDuration)||selectedDuration<=0||Number(sourceRange.endSeconds)>sourceDurationS+0.05)throw new Error("The confirmed range no longer fits the available source metadata.");
  if(Number(sourceRange.startSeconds)-mediaOffsetSeconds<0||Number(sourceRange.endSeconds)-mediaOffsetSeconds>mediaDuration+0.05)throw new Error("The prepared media does not cover the confirmed analysis range.");
  const continueAfterRange=selectedDuration>MAX_SOURCE_CHUNK_SECONDS;
  const initialCursor=Number(sourceRange.startSeconds)-mediaOffsetSeconds;
  await completeJobAndEnqueue(j.id,{
    userId:j.userId,projectId:j.projectId,type:"TRANSCRIBE",
    payload:{mediaAssetId:asset.id,sourceRange,sourceDurationS,mediaOffsetSeconds,rangeLimitedDownload:isRangeLimitedDownload,rangeConfirmed:Boolean(p.rangeConfirmed),rangeCursorSeconds:initialCursor,continueAfterRange},
  });
  return;
}
if(j.type==="TRANSCRIBE"){
  await setJobProgress(j.id,.1,"TRANSCRIBING");
  const p=j.payload as any;
  const project=await db.project.findUniqueOrThrow({where:{id:j.projectId!},select:{outputLanguage:true,mode:true}});
  const asset=await db.mediaAsset.findUniqueOrThrow({where:{id:p.mediaAssetId}});
  const sourceDurationS=Number(p.sourceDurationS??asset.durationS??0);
  const mediaOffsetSeconds=Number(p.mediaOffsetSeconds||0);
  const sourceRange=p.sourceRange||{startSeconds:0,endSeconds:sourceDurationS};
  if(p.sourceRange&&p.rangeConfirmed){
    const subscription=await db.subscription.findUnique({where:{userId:j.userId},select:{plan:true,status:true}});
    validateAnalysisRange({startSeconds:sourceRange.startSeconds,endSeconds:sourceRange.endSeconds,sourceDurationSeconds:sourceDurationS,entitlement:analysisEntitlement(subscription)});
  }
  const chunk=nextRangeChunk({sourceStartSeconds:Number(sourceRange.startSeconds),sourceEndSeconds:Number(sourceRange.endSeconds),mediaOffsetSeconds,mediaDurationSeconds:Number(asset.durationS||0),cursorSeconds:Number(p.rangeCursorSeconds??(Number(sourceRange.startSeconds)-mediaOffsetSeconds))});
  const continueAfterRange=chunk.hasNext;
  let transcript=await db.transcript.findFirst({where:{mediaAssetId:p.mediaAssetId,AND:[
    {metadata:{path:["sourceStartS"],equals:chunk.sourceStartSeconds}},
    {metadata:{path:["sourceEndS"],equals:chunk.sourceEndSeconds}},
  ]},orderBy:{createdAt:"desc"}});
  let duration=Number((transcript?.metadata as any)?.duration||0);
  if(!transcript){
    const localMedia=await ensureLocalStorage(asset.storageKey);
    await setJobProgress(j.id,.2,"TRANSCRIBING");
    const result=await ai("/v1/transcribe",{media_path:localMedia,language:project.outputLanguage||undefined,start_seconds:chunk.localStartSeconds,end_seconds:chunk.localEndSeconds},STAGE_TIMEOUT_MS.TRANSCRIBE);
    await setJobProgress(j.id,.85,"TRANSCRIBING");
    await assertJobNotCancelled(j.id);
    const sourceSegments=toSourceTimestamps(result.segments||[],mediaOffsetSeconds);
    transcript=await db.transcript.create({data:{
      mediaAssetId:p.mediaAssetId,language:result.language,text:result.text,
      metadata:{duration:result.duration,sourceStartS:chunk.sourceStartSeconds,sourceEndS:chunk.sourceEndSeconds,sourceDurationS,mediaOffsetSeconds},
      segments:{create:sourceSegments.map((s:any)=>({
        startS:s.start,endS:s.end,text:s.text,confidence:s.confidence,
        words:{create:(s.words||[]).map((w:any)=>({
          startS:w.start,endS:w.end,word:w.word,confidence:w.confidence,
        }))},
      }))},
    }});
    duration=Number(result.duration||0);
    await db.usage.update({where:{userId:j.userId},data:{minutesAnalyzed:{increment:duration/60}}}).catch(()=>{});
  }
  await assertJobNotCancelled(j.id);
  await completeJobAndEnqueue(j.id,{
    userId:j.userId,projectId:j.projectId,
    type:project.mode==="LONG_FORM"?"LONGFORM_ANALYZE":"ANALYZE",
    payload:{transcriptId:transcript.id,mediaAssetId:asset.id,sourceRange,sourceDurationS,mediaOffsetSeconds,rangeLimitedDownload:Boolean(p.rangeLimitedDownload),rangeConfirmed:Boolean(p.rangeConfirmed),localStartSeconds:chunk.localStartSeconds,localEndSeconds:chunk.localEndSeconds,sourceChunkStartSeconds:chunk.sourceStartSeconds,sourceChunkEndSeconds:chunk.sourceEndSeconds,rangeCursorSeconds:chunk.nextCursorSeconds,continueAfterRange},
  });
  return;
}
if(j.type==="LONGFORM_ANALYZE"){
  const p=j.payload as any;
  const transcript=await db.transcript.findUniqueOrThrow({where:{id:p.transcriptId},include:{segments:true}});
  const project=await db.project.findUniqueOrThrow({where:{id:j.projectId!}});
  const instructionLines=(project.customInstructions||"").split("\n");
  const genreLine=instructionLines.find((line:string)=>line.startsWith("Content genre:"))||"";
  const genre=genreLine.replace("Content genre:","").trim()||"auto";
  const instruction=instructionLines.filter((line:string)=>!line.startsWith("Clip categories:")&&!line.startsWith("Content genre:")).join("\n").trim()||undefined;
  const sourceAsset=project.sourceId?await db.mediaAsset.findFirst({where:{sourceId:project.sourceId}}):null;
  const mediaPath=sourceAsset?await ensureLocalStorage(sourceAsset.storageKey):undefined;
  const mediaOffset=Number(p.mediaOffsetSeconds||0);
  await setJobProgress(j.id,.2,"ANALYZING");
  const result=await ai("/v1/longform",{segments:toMediaLocalSegments(transcript.segments.map((segment:any)=>({start:segment.startS,end:segment.endS,text:segment.text})),mediaOffset),instruction,genre,media_path:mediaPath},STAGE_TIMEOUT_MS.ANALYZE);
  await setJobProgress(j.id,.85,"ANALYZING");
  await assertJobNotCancelled(j.id);
  const stories=toSourceTimestamps((result.stories||[]) as any[],mediaOffset);
  for(const story of stories){
    const exists=await db.clip.findFirst({where:{projectId:project.id,category:"long_form_story",startS:story.start,endS:story.end},select:{id:true}});
    if(!exists)await db.clip.create({data:{projectId:project.id,startS:story.start,endS:story.end,score:story.score,category:"long_form_story",title:story.title,status:"CANDIDATE",metadata:{rationale:story.rationale,features:story.features}}});
  }
  if(sourceAsset){
    const prior=await db.longFormDocument.findUnique({where:{projectId:project.id}});
    const priorChapters=Array.isArray(prior?.chapters)?prior.chapters as Array<{start:number;title:string}>:[];
    const nextChapters=(result.chapters||[]).map((chapter:any)=>({start:Number(chapter.start)+mediaOffset,title:chapter.title}));
    const chapters=[...new Map([...priorChapters,...nextChapters].map((chapter)=>[`${chapter.start}:${chapter.title}`,chapter])).values()].sort((a,b)=>a.start-b.start);
    const transcripts=await db.transcript.findMany({where:{mediaAssetId:sourceAsset.id},include:{segments:true}});
    const sourceStart=Number(p.sourceRange?.startSeconds||0),sourceEnd=Number(p.sourceRange?.endSeconds||sourceAsset.durationS||0);
    const text=transcripts.flatMap((item:any)=>item.segments).filter((segment:any)=>segment.endS>sourceStart&&segment.startS<sourceEnd).sort((a:any,b:any)=>a.startS-b.startS).map((segment:any)=>segment.text).join(" ");
    const description=text.length>500?text.slice(0,497).trimEnd()+"...":text;
    const thumbnailKey="long-form/"+project.id+"/thumbnail.jpg";
    if(!prior){
      const thumbnailPath=path.resolve(process.env.MEDIA_STORAGE_ROOT||"../storage",thumbnailKey);
      await ai("/v1/thumbnail",{input_path:await ensureLocalStorage(sourceAsset.storageKey),output_path:thumbnailPath,time:Number(result.chapters?.[0]?.start||0)},STAGE_TIMEOUT_MS.PROBE);
      await assertJobNotCancelled(j.id);
      await putFile(thumbnailKey,thumbnailPath,"image/jpeg");
    }
    await db.longFormDocument.upsert({where:{projectId:project.id},create:{projectId:project.id,transcriptId:transcript.id,title:prior?.title||result.title,description,chapters,thumbnailKey:prior?.thumbnailKey||thumbnailKey},update:{transcriptId:transcript.id,title:prior?.title||result.title,description,chapters,thumbnailKey:prior?.thumbnailKey||thumbnailKey}});
  }
  await assertJobNotCancelled(j.id);
  await finishAnalysisAndQueueNext(j,p,p.mediaAssetId||transcript.mediaAssetId);
  return;
}
 if(j.type==="ANALYZE"){
  const p=j.payload as any;
  const t=await db.transcript.findUniqueOrThrow({where:{id:p.transcriptId},include:{segments:true}});
  const project=await db.project.findUniqueOrThrow({where:{id:j.projectId!}});
  const sourceRange=p.sourceRange||null;
  const analysisVersion="2.4.0-range-"+String(Number(p.sourceChunkStartSeconds||sourceRange?.startSeconds||0))+"-"+String(Number(p.sourceChunkEndSeconds||sourceRange?.endSeconds||0));
  const existing=await db.analysis.findFirst({
    where:{projectId:project.id,model:"multimodal-heuristic-v2",version:analysisVersion},
    select:{id:true},
  });
  if(existing){
    await assertJobNotCancelled(j.id);
    await finishAnalysisAndQueueNext(j,p,p.mediaAssetId||t.mediaAssetId);
    return;
  }
  const instructionLines=(project.customInstructions||"").split("\n");
  const categoryLine=instructionLines.find((x:string)=>x.startsWith("Clip categories:"))||"";
  const genreLine=instructionLines.find((x:string)=>x.startsWith("Content genre:"))||"";
  const genre=genreLine.replace("Content genre:","").trim()||"auto";
  const categories=categoryLine.replace("Clip categories:","").split(",").map((x:string)=>x.trim()).filter(Boolean);
  const instructions=instructionLines.filter((x:string)=>!x.startsWith("Clip categories:")&&!x.startsWith("Content genre:")).join("\n").trim()||undefined;
  await setJobProgress(j.id,.15,"ANALYZING");
  const mediaAsset=await db.mediaAsset.findUniqueOrThrow({where:{id:t.mediaAssetId}});
  const mediaOffsetSeconds=Number(p.mediaOffsetSeconds||0);
  const localStartSeconds=Number(p.localStartSeconds??(Number(p.sourceChunkStartSeconds||0)-mediaOffsetSeconds));
  const localEndSeconds=Number(p.localEndSeconds??(Number(p.sourceChunkEndSeconds||0)-mediaOffsetSeconds));
  const sourceChunkStartSeconds=Number(p.sourceChunkStartSeconds??sourceRange?.startSeconds??0);
  const sourceChunkEndSeconds=Number(p.sourceChunkEndSeconds??sourceRange?.endSeconds??Number(mediaAsset.durationS||0));
  const feedback=await loadCreatorFeedbackProfile(j.userId);
  await setJobProgress(j.id,.35,"ANALYZING");
  const result=await ai("/v1/analyze",{
    segments:toMediaLocalSegments(t.segments.map(s=>({start:s.startS,end:s.endS,text:s.text})),mediaOffsetSeconds),
    instruction:instructions,categories,genre,
    media_path:await ensureLocalStorage(mediaAsset.storageKey),
    ...(p.localStartSeconds!==undefined?{start_seconds:localStartSeconds,end_seconds:localEndSeconds}:{}),
    creator_preferences:feedback.active?feedback.weights:{},
  },STAGE_TIMEOUT_MS.ANALYZE);
  await setJobProgress(j.id,.85,"ANALYZING");
  await assertJobNotCancelled(j.id);
  const mappedCandidates=Array.isArray(result.candidates)?(p.localStartSeconds!==undefined?toSourceTimestamps(result.candidates,mediaOffsetSeconds):result.candidates):[];
  const candidates=mappedCandidates.filter((c:any)=>{
    const start=Number(c.start),end=Number(c.end);
    return Number.isFinite(start)&&Number.isFinite(end)&&start>=sourceChunkStartSeconds&&end<=sourceChunkEndSeconds&&(!sourceRange||(start>=Number(sourceRange.startSeconds)&&end<=Number(sourceRange.endSeconds)));
  });
  await db.analysis.create({data:{
    projectId:project.id,model:"multimodal-heuristic-v2",version:analysisVersion,
    metadata:{
      candidateCount:candidates.length,
      creatorFeedback:{
        active:feedback.active,acceptedSamples:feedback.acceptedSamples,
        rejectedSamples:feedback.rejectedSamples,signalsLearned:Object.keys(feedback.weights).length,
      },
    },
    highlights:{create:candidates.map((c:any)=>({
      startS:Number(c.start),endS:Number(c.end),score:Number(c.score)||0,
      category:String(c.category||"AI Detect"),rationale:String(c.rationale||""),
      features:c.features||{},
      clip:{create:{
        project:{connect:{id:project.id}},
        startS:Number(c.start),endS:Number(c.end),score:Number(c.score)||0,
        title:typeof c.title==="string"&&c.title.trim()?c.title.trim().slice(0,120):undefined,
        category:String(c.category||"AI Detect"),status:"CANDIDATE",
      }},
    }))},
  }});
  await assertJobNotCancelled(j.id);
  await finishAnalysisAndQueueNext(j,p,p.mediaAssetId||t.mediaAssetId);
  log("info","stage_completed",{jobId:j.id,type:"ANALYZE"});
  return;
}
if(j.type==="LONGFORM_RENDER"){const p=j.payload as any;const doc=await db.longFormDocument.findUniqueOrThrow({where:{id:p.documentId},include:{project:{include:{source:{include:{media:true}}}}}});const asset=doc.project.source?.media[0];if(!asset)throw new Error("Long-form source media missing");await db.longFormDocument.update({where:{id:doc.id},data:{renderStatus:"PROCESSING"}});const outputKey="long-form/"+doc.projectId+"/render-"+Date.now()+".mp4";const outputPath=path.resolve(process.env.MEDIA_STORAGE_ROOT||"../storage",outputKey);const ingest=await db.job.findFirst({where:{projectId:doc.projectId,type:"INGEST"},orderBy:{createdAt:"desc"},select:{payload:true}});const ingestPayload=(ingest?.payload||{}) as any;const mediaOffset=ingestPayload.rangeLimitedDownload?Number(ingestPayload.sourceRange?.startSeconds||0):0;const transcripts=await db.transcript.findMany({where:{mediaAssetId:asset.id},include:{segments:true}});const captions=transcripts.flatMap((transcript:any)=>transcript.segments).map((s:any)=>({start:Math.max(0,Number(s.startS)-mediaOffset),end:Math.max(0,Number(s.endS)-mediaOffset),text:s.text})).filter((c:any)=>c.end>c.start);const mediaPath=await ensureLocalStorage(asset.storageKey);await ai("/v1/render",{input_path:mediaPath,output_path:outputPath,start:0,end:Number(asset.durationS||0),aspect:"16:9",segments:[{start:0,end:Number(asset.durationS||0)}],captions},STAGE_TIMEOUT_MS.RENDER);await assertJobNotCancelled(j.id);await putFile(outputKey,outputPath,"video/mp4");await db.longFormDocument.update({where:{id:doc.id},data:{renderStatus:"READY",renderKey:outputKey}});await assertJobNotCancelled(j.id);await finishJob(j.id);log("info","job_finished",{jobId:j.id,type:j.type});return}
 if(j.type==="PUBLISH"){const p=j.payload as any;const post=await db.scheduledPost.findUniqueOrThrow({where:{id:p.scheduledPostId},include:{socialConnection:true,clip:{include:{renders:{where:{status:"READY"},orderBy:{createdAt:"desc"},take:1}}}}});if(!post.socialConnection||!post.clip?.renders[0])throw new Error("Publish prerequisites are not ready");const render=post.clip.renders[0];const filePath=path.resolve(process.env.MEDIA_STORAGE_ROOT||"../storage",render.storageKey!);const meta=(post.metadata||{}) as any;const result=post.socialConnection.provider==="youtube"?await publishYouTube(j.userId,filePath,{title:String(meta.title||"Clip"),description:String(meta.description||""),privacyStatus:"private"}):await publishTikTok(j.userId,filePath,String(meta.title||"Clip"));if(post.socialConnection.provider==="tiktok"){await db.scheduledPost.update({where:{id:post.id},data:{status:"PUBLISHING",platformPostId:result.platformPostId,error:null}});await db.job.create({data:{userId:j.userId,projectId:post.clip?.projectId,type:"PUBLISH_STATUS",payload:{scheduledPostId:post.id},runAfter:new Date(Date.now()+30000)}});}else{await db.scheduledPost.update({where:{id:post.id},data:{status:"PUBLISHED",platformPostId:result.platformPostId,error:null}});}await db.creatorEvent.create({data:{userId:j.userId,projectId:post.clip?.projectId,event:"PUBLISH",metadata:{scheduledPostId:post.id,clipId:post.clipId,provider:post.socialConnection.provider,platformPostId:result.platformPostId}}});await assertJobNotCancelled(j.id);await finishJob(j.id);log("info","job_finished",{jobId:j.id,type:j.type});return}
 if(j.type==="PUBLISH_STATUS"){const p=j.payload as any;const post=await db.scheduledPost.findUniqueOrThrow({where:{id:p.scheduledPostId}});if(post.status!=="PUBLISHING"){await assertJobNotCancelled(j.id);await finishJob(j.id);return}if(!post.platformPostId)throw new Error("Missing TikTok publish id");const state=await tiktokPublishStatus(j.userId,post.platformPostId);if(state.status==="PUBLISH_COMPLETE"){await db.scheduledPost.update({where:{id:post.id},data:{status:"PUBLISHED",platformPostId:state.postId||post.platformPostId,error:null}});await assertJobNotCancelled(j.id);await finishJob(j.id);log("info","job_finished",{jobId:j.id,type:j.type});return}if(state.status==="FAILED"){await db.scheduledPost.update({where:{id:post.id},data:{status:"FAILED",error:state.reason||"TikTok publish failed"}});await assertJobNotCancelled(j.id);await finishJob(j.id);log("warn","job_finished_failed",{jobId:j.id,type:j.type});return}await db.job.create({data:{userId:j.userId,projectId:post.clipId?((await db.clip.findUnique({where:{id:post.clipId},select:{projectId:true}}))?.projectId):undefined,type:"PUBLISH_STATUS",payload:{scheduledPostId:post.id},runAfter:new Date(Date.now()+30000)}});await assertJobNotCancelled(j.id);await finishJob(j.id);return}
if(j.type==="RENDER"){const p=j.payload as any;const priorRender=await db.render.findUniqueOrThrow({where:{id:p.renderId}});if(priorRender.status==="READY"&&priorRender.storageKey){await assertJobNotCancelled(j.id);await finishJob(j.id);log("info","job_finished",{jobId:j.id,type:j.type});return}const clip=await db.clip.findUniqueOrThrow({where:{id:p.clipId},include:{project:{include:{source:{include:{media:true}}}},edit:true,highlight:true,captions:{orderBy:{createdAt:"desc"},take:1}}});const asset=clip.project.source?.media[0];if(!asset)throw new Error("Source media missing");const seg=(clip.edit?.segments as any[])?.[0];if(!seg)throw new Error("Clip edit missing");const outputKey="renders/"+clip.id+"-"+Date.now()+".mp4";const outputPath=path.resolve(process.env.MEDIA_STORAGE_ROOT||"../storage",outputKey);await db.render.update({where:{id:p.renderId},data:{status:"PROCESSING",error:null}});const editSegments=(clip.edit?.segments as any[]).map((s:any)=>({start:Number(s.startS),end:Number(s.endS)}));const ingest=await db.job.findFirst({where:{projectId:clip.projectId,type:"INGEST"},orderBy:{createdAt:"desc"},select:{payload:true}});const ingestPayload=(ingest?.payload||{}) as any;const mediaOffset=ingestPayload.rangeLimitedDownload?Number(ingestPayload.sourceRange?.startSeconds||0):0;const renderSegments=editSegments.map((s:any)=>({start:s.start-mediaOffset,end:s.end-mediaOffset}));const renderedDuration=editSegments.reduce((sum,s)=>sum+Math.max(0,s.end-s.start),0);const transcript=await db.transcript.findFirst({where:{mediaAssetId:asset.id},include:{segments:true}});const track=clip.captions?.[0];const sourceCues=Array.isArray(track?.cues)&&(track?.cues as any[]).length?(track?.cues as any[]):undefined;let captionOffset=0;const captions:(Array<{start:number;end:number;text:string}>)=[];for(const e of editSegments){const eStart=Number(e.start),eEnd=Number(e.end);for(const s of (sourceCues||[])){const start=Number(s.startS??s.start)+Number(clip.startS),end=Number(s.endS??s.end)+Number(clip.startS);if(start>=eEnd||end<=eStart)continue;const cs=Math.max(start,eStart),ce=Math.min(end,eEnd);if(ce>cs)captions.push({start:captionOffset+cs-eStart,end:captionOffset+ce-eStart,text:String(s.text||"")});}if(!sourceCues){for(const s of transcript?.segments||[]){const start=Number(s.startS),end=Number(s.endS);if(start>=eEnd||end<=eStart)continue;const cs=Math.max(start,eStart),ce=Math.min(end,eEnd);if(ce>cs)captions.push({start:captionOffset+cs-eStart,end:captionOffset+ce-eStart,text:s.text});}}captionOffset+=Math.max(0,eEnd-eStart);}await setJobProgress(j.id,.15,"RENDERING");const r=await ai("/v1/render",{input_path:await ensureLocalStorage(asset.storageKey),output_path:outputPath,start:Number(seg.startS)-mediaOffset,end:Number(seg.endS)-mediaOffset,aspect:clip.edit?.aspectRatio||"9:16",segments:renderSegments,captions,caption_style:(track?.style as any)||{},focus_x:Number((clip.highlight?.features as any)?.faceFocusX??0.5)},STAGE_TIMEOUT_MS.RENDER);await assertJobNotCancelled(j.id);await putFile(outputKey,outputPath,"video/mp4");await setJobProgress(j.id,.9,"RENDERING");await db.render.update({where:{id:p.renderId},data:{status:"READY",storageKey:outputKey,mimeType:"video/mp4",durationS:renderedDuration}});await db.clip.update({where:{id:clip.id},data:{status:"READY"}});await db.usage.update({where:{userId:j.userId},data:{renders:{increment:1}}}).catch(()=>{});await assertJobNotCancelled(j.id);await finishJob(j.id);log("info","job_finished",{jobId:j.id,type:j.type});return}
  throw new Error("Unknown job type: "+j.type)
}catch(e){const message=e instanceof Error?e.message:String(e);log("error","job_failed",{jobId:j.id,type:j.type,error:message});const current=await db.job.findUnique({where:{id:j.id},select:{status:true}});if(current?.status==="CANCELLED")return;const failed=await failJob(j.id,message,{retryable:!isPermanentFailure(e)});if(failed?.status==="FAILED"){const p=j.payload as any;if(j.type==="PUBLISH"&&p?.scheduledPostId)await db.scheduledPost.update({where:{id:p.scheduledPostId},data:{status:"FAILED",error:message}}).catch(()=>{});if(j.type==="RENDER"&&p?.renderId)await db.render.update({where:{id:p.renderId},data:{status:"FAILED",error:message}}).catch(()=>{});if(j.type==="LONGFORM_RENDER"&&p?.documentId)await db.longFormDocument.update({where:{id:p.documentId},data:{renderStatus:"FAILED"}}).catch(()=>{});}}finally{clearInterval(heartbeat)}
}
async function main(){log("info","worker_started",{aiUrl:AI});for(;;){await tick();await sleep(1000)}}main().catch(e=>{log("error","worker_crashed",{error:e instanceof Error?e.message:String(e)});process.exit(1)});
