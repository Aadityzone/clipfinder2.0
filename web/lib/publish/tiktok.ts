import{stat,createReadStream}from"node:fs";import{accessTokenFor}from"../social";import{Readable}from"node:stream";
const CHUNK=10_000_000;
export async function publishTikTok(userId:string,filePath:string,title:string){
 const token=await accessTokenFor(userId,"tiktok");const info=await stat(filePath);
 const creator=await fetch("https://open.tiktokapis.com/v2/post/publish/creator_info/query/",{method:"POST",headers:{Authorization:"Bearer "+token,"Content-Type":"application/json"}}).then(r=>r.json());
 const privacy=creator.data?.privacy_level_options?.[0];if(!privacy)throw new Error("TikTok did not return a valid privacy option");
 const chunkSize=info.size<5_000_000?info.size:Math.min(CHUNK,64_000_000);const total=Math.max(1,Math.ceil(info.size/chunkSize));
 const init=await fetch("https://open.tiktokapis.com/v2/post/publish/video/init/",{method:"POST",headers:{Authorization:"Bearer "+token,"Content-Type":"application/json"},body:JSON.stringify({post_info:{title:title.slice(0,2200),privacy_level:privacy,disable_comment:false,disable_duet:false,disable_stitch:false},source_info:{source:"FILE_UPLOAD",video_size:info.size,chunk_size:chunkSize,total_chunk_count:total}})});
 const data=await init.json();if(!init.ok||!data.data?.upload_url)throw new Error("TikTok upload initialization failed: "+JSON.stringify(data));
 for(let start=0;start<info.size;start+=chunkSize){const end=Math.min(info.size-1,start+chunkSize-1);const body=Readable.toWeb(createReadStream(filePath,{start,end})) as any;const upload=await fetch(data.data.upload_url,{method:"PUT",headers:{"Content-Type":"video/mp4","Content-Length":String(end-start+1),"Content-Range":`bytes ${start}-${end}/${info.size}`},body,duplex:"half"} as any);if(!upload.ok)throw new Error("TikTok media upload failed: "+await upload.text())}
 return{platformPostId:data.data.publish_id,state:"PUBLISHING"};
}
export async function tiktokPublishStatus(userId:string,publishId:string){
 const token=await accessTokenFor(userId,"tiktok");
 const r=await fetch("https://open.tiktokapis.com/v2/post/publish/status/fetch/",{method:"POST",headers:{Authorization:"Bearer "+token,"Content-Type":"application/json"},body:JSON.stringify({publish_id:publishId})});
 const d=await r.json();if(!r.ok)throw new Error("TikTok status failed: "+JSON.stringify(d));return{status:String(d.data?.status||"UNKNOWN"),postId:d.data?.publicaly_available_post_id?.[0]?String(d.data.publicaly_available_post_id[0]):null,reason:d.data?.fail_reason};
}
