import { createReadStream, createWriteStream, existsSync } from "node:fs";
import { mkdir, stat, writeFile, unlink, rename } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { pipeline } from "node:stream/promises";
import { S3Client, GetObjectCommand, HeadObjectCommand, HeadBucketCommand, DeleteObjectCommand } from "@aws-sdk/client-s3";
import { Upload } from "@aws-sdk/lib-storage";

export function storageRoot(){return path.resolve(process.env.MEDIA_STORAGE_ROOT||"../storage")}
export function storagePath(key:string){
  if(!key || key.includes("\0"))throw new Error("Storage key must be a non-empty relative path");
  // Reject Windows drive/UNC paths even when the app runs on POSIX, where
  // path.resolve would otherwise treat them as harmless relative filenames.
  if(/^[a-zA-Z]:[\\/]/.test(key)||key.startsWith("\\\\" )||key.startsWith("//")){
    throw new Error("Storage key must stay within MEDIA_STORAGE_ROOT");
  }
  const root=storageRoot();
  const target=path.resolve(root,key);
  const relative=path.relative(root,target);
  if(!relative||relative===".."||relative.startsWith(".."+path.sep)||path.isAbsolute(relative)){
    throw new Error("Storage key must stay within MEDIA_STORAGE_ROOT");
  }
  return target;
}
export function isObjectStorage(){return (process.env.STORAGE_PROVIDER||"local").toLowerCase()==="s3"}
function s3Config(){
  const bucket=process.env.S3_BUCKET;
  if(!bucket)throw new Error("S3_BUCKET is required when STORAGE_PROVIDER=s3");
  return {bucket};
}
function s3(){
  return new S3Client({
    region:process.env.S3_REGION||"auto",
    endpoint:process.env.S3_ENDPOINT||undefined,
    forcePathStyle:process.env.S3_FORCE_PATH_STYLE==="true",
    credentials:process.env.S3_ACCESS_KEY_ID&&process.env.S3_SECRET_ACCESS_KEY?{accessKeyId:process.env.S3_ACCESS_KEY_ID,secretAccessKey:process.env.S3_SECRET_ACCESS_KEY}:undefined,
  });
}
export async function checkStorageHealth():Promise<void>{
  if(isObjectStorage()){
    const {bucket}=s3Config();
    const client=s3();
    try{await client.send(new HeadBucketCommand({Bucket:bucket}));}
    finally{client.destroy();}
    return;
  }
  const root=storageRoot();
  await mkdir(root,{recursive:true});
  const probe=path.join(root,".health-"+randomUUID());
  try{await writeFile(probe,"ok",{flag:"wx"});}
  finally{await unlink(probe).catch(()=>{});}
}
export async function ensureStorage(){await mkdir(storageRoot(),{recursive:true})}
export async function saveStream(key:string,stream:NodeJS.ReadableStream){
  await ensureStorage();
  const target=storagePath(key);
  await mkdir(path.dirname(target),{recursive:true});
  // Never expose a partially-written upload at its final key. Readers can see
  // either the previous complete file or the new complete file after rename.
  const temporary=target+".upload-"+randomUUID()+".tmp";
  try{
    await pipeline(stream as any,createWriteStream(temporary,{flags:"wx"}));
    // In S3 mode, publish the durable object from the completed temporary file
    // before replacing the local cache. A failed S3 write leaves the old cache
    // untouched and never exposes a partial upload at the final key.
    if(isObjectStorage())await putFile(key,temporary);
    await rename(temporary,target);
    return target;
  }catch(error){
    await unlink(temporary).catch(()=>{});
    throw error;
  }
}
export async function putFile(key:string,filePath:string,mimeType?:string){
  if(!isObjectStorage())return;
  const {bucket}=s3Config();
  const client=s3();
  try{
    await new Upload({client,params:{Bucket:bucket,Key:key,Body:createReadStream(filePath),ContentType:mimeType}}).done();
  }finally{
    client.destroy();
  }
}
export async function ensureLocalStorage(key:string){
  const file=storagePath(key);
  if(existsSync(file))return file;
  if(!isObjectStorage())throw new Error("Storage file not found: "+key);
  await mkdir(path.dirname(file),{recursive:true});
  const temporary=file+".download-"+randomUUID()+".tmp";
  const client=s3();
  try{
    const {bucket}=s3Config();
    const out=await client.send(new GetObjectCommand({Bucket:bucket,Key:key}));
    if(!out.Body)throw new Error("Object storage returned no body");
    // Do not leave a truncated cache file behind if a remote stream fails.
    // Publish the local copy atomically only after the full body is written.
    await pipeline(out.Body as any,createWriteStream(temporary,{flags:"wx"}));
    await rename(temporary,file);
    return file;
  }catch(error){
    await unlink(temporary).catch(()=>{});
    throw error;
  }finally{
    client.destroy();
  }
}
export async function headStorage(key:string){
  if(!isObjectStorage()){const s=await stat(storagePath(key));return {size:s.size,contentType:undefined as string|undefined}}
  const {bucket}=s3Config();
  const client=s3();
  try{
    const h=await client.send(new HeadObjectCommand({Bucket:bucket,Key:key}));
    return {size:Number(h.ContentLength||0),contentType:h.ContentType};
  }finally{
    client.destroy();
  }
}
export async function getStorageRange(key:string,start?:number,end?:number){
  if(!isObjectStorage())return {body:(await import("node:stream")).Readable.toWeb(createReadStream(storagePath(key),start===undefined?undefined:{start,end})) as any,size:(await stat(storagePath(key))).size,contentType:undefined as string|undefined};
  const {bucket}=s3Config();const Range=start===undefined?undefined:`bytes=${start}-${end??""}`;
  const client=s3();
  try{
    const o=await client.send(new GetObjectCommand({Bucket:bucket,Key:key,Range}));
    return {body:o.Body as any,size:Number(o.ContentLength||0),contentType:o.ContentType};
  }catch(error){
    client.destroy();
    throw error;
  }
}
export async function deleteStorage(key:string){
  const file=storagePath(key);
  if(isObjectStorage()){
    const {bucket}=s3Config();
    const client=s3();
    try{await client.send(new DeleteObjectCommand({Bucket:bucket,Key:key}));}
    finally{client.destroy();}
  }
  await unlink(file).catch((error:any)=>{if(error?.code!=="ENOENT")throw error});
}
export function openStorage(key:string){return createReadStream(storagePath(key))}
