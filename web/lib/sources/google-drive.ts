import{db}from"../db";import{unseal}from"../oauth";import{createWriteStream}from"node:fs";import{mkdir}from"node:fs/promises";import path from"node:path";import{Readable}from"node:stream";import{pipeline}from"node:stream/promises";

export async function downloadGoogleDrive(userId:string,fileId:string,outputPath:string){
 const connection=await db.socialConnection.findFirst({where:{userId,provider:"google_drive"}});
 if(!connection)throw new Error("Connect Google Drive first");
 const token=unseal(connection.accessToken);
 const meta=await fetch(`https://www.googleapis.com/drive/v3/files/${encodeURIComponent(fileId)}?fields=id,name,mimeType,size`,{headers:{Authorization:"Bearer "+token}}).then(async r=>{if(!r.ok)throw new Error("Google Drive metadata failed: "+await r.text());return r.json()});
 if(!String(meta.mimeType||"").startsWith("video/")&&!String(meta.mimeType||"").startsWith("audio/"))throw new Error("Selected Drive file is not video/audio");
 await mkdir(path.dirname(outputPath),{recursive:true});
 const r=await fetch(`https://www.googleapis.com/drive/v3/files/${encodeURIComponent(fileId)}?alt=media`,{headers:{Authorization:"Bearer "+token}});
 if(!r.ok||!r.body)throw new Error("Google Drive download failed: "+await r.text());
 await pipeline(Readable.fromWeb(r.body as any),createWriteStream(outputPath));
 return{...meta,path:outputPath};
}
export async function getGoogleDriveMetadata(userId:string,url:string){
 const match=url.match(/(?:\/file\/d\/|[?&]id=)([A-Za-z0-9_-]+)/);
 if(!match)throw new Error("Invalid Google Drive video URL.");
 const connection=await db.socialConnection.findFirst({where:{userId,provider:"google_drive"}});
 if(!connection)throw new Error("Connect Google Drive first to inspect this file.");
 const token=unseal(connection.accessToken);
 const response=await fetch(`https://www.googleapis.com/drive/v3/files/${encodeURIComponent(match[1])}?fields=id,name,mimeType,thumbnailLink,videoMediaMetadata(durationMillis)`,{headers:{Authorization:"Bearer "+token},signal:AbortSignal.timeout(15000)});
 if(!response.ok)throw new Error("Google Drive metadata could not be retrieved. Confirm the file is shared with your connected account.");
 const meta=await response.json();
 if(!String(meta.mimeType||"").startsWith("video/"))throw new Error("The selected Google Drive file is not a video.");
 const duration=Number(meta.videoMediaMetadata?.durationMillis)/1000;
 if(!Number.isFinite(duration)||duration<=0)throw new Error("Google Drive has not provided a usable video duration for this file.");
 return{title:String(meta.name||"Video"),platform:"Google Drive",duration,thumbnail:typeof meta.thumbnailLink==="string"?meta.thumbnailLink:null};
}
export async function listGoogleDriveVideos(userId:string){
 const connection=await db.socialConnection.findFirst({where:{userId,provider:"google_drive"}});
 if(!connection)throw new Error("Connect Google Drive first");
 const token=unseal(connection.accessToken);
 const q="trashed = false and (mimeType contains 'video/' or mimeType contains 'audio/')";
 const r=await fetch("https://www.googleapis.com/drive/v3/files?"+new URLSearchParams({q,fields:"files(id,name,mimeType,size,modifiedTime,webViewLink)",pageSize:"100",orderBy:"modifiedTime desc"}),{headers:{Authorization:"Bearer "+token}});
 if(!r.ok)throw new Error("Google Drive listing failed: "+await r.text());
 return(await r.json()).files||[];
}
