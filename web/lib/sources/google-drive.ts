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
export async function listGoogleDriveVideos(userId:string){
 const connection=await db.socialConnection.findFirst({where:{userId,provider:"google_drive"}});
 if(!connection)throw new Error("Connect Google Drive first");
 const token=unseal(connection.accessToken);
 const q="trashed = false and (mimeType contains 'video/' or mimeType contains 'audio/')";
 const r=await fetch("https://www.googleapis.com/drive/v3/files?"+new URLSearchParams({q,fields:"files(id,name,mimeType,size,modifiedTime,webViewLink)",pageSize:"100",orderBy:"modifiedTime desc"}),{headers:{Authorization:"Bearer "+token}});
 if(!r.ok)throw new Error("Google Drive listing failed: "+await r.text());
 return(await r.json()).files||[];
}
