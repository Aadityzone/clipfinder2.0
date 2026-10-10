import { createReadStream, createWriteStream, existsSync } from "node:fs";
import { mkdir, stat, writeFile, unlink } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { S3Client, GetObjectCommand, HeadObjectCommand, HeadBucketCommand } from "@aws-sdk/client-s3";
import { Upload } from "@aws-sdk/lib-storage";

export function storageRoot(){return path.resolve(process.env.MEDIA_STORAGE_ROOT||"../storage")}
export function storagePath(key:string){return path.join(storageRoot(),key.replace(/^[/\\\\]+/,""))}
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
  await ensureStorage();const target=storagePath(key);await mkdir(path.dirname(target),{recursive:true});
  await new Promise<void>((resolve,reject)=>{const out=createWriteStream(target);stream.pipe(out);out.on("finish",resolve);out.on("error",reject);stream.on("error",reject)});
  if(isObjectStorage())await putFile(key,target);
  return target;
}
export async function putFile(key:string,filePath:string,mimeType?:string){
  if(!isObjectStorage())return;
  const {bucket}=s3Config();
  await new Upload({client:s3(),params:{Bucket:bucket,Key:key,Body:createReadStream(filePath),ContentType:mimeType}}).done();
}
export async function ensureLocalStorage(key:string){
  const file=storagePath(key);
  if(existsSync(file))return file;
  if(!isObjectStorage())throw new Error("Storage file not found: "+key);
  await mkdir(path.dirname(file),{recursive:true});
  const {bucket}=s3Config();
  const out=await s3().send(new GetObjectCommand({Bucket:bucket,Key:key}));
  if(!out.Body)throw new Error("Object storage returned no body");
  await new Promise<void>((resolve,reject)=>{const ws=createWriteStream(file);(out.Body as any).pipe(ws);ws.on("finish",resolve);ws.on("error",reject)});
  return file;
}
export async function headStorage(key:string){
  if(!isObjectStorage()){const s=await stat(storagePath(key));return {size:s.size,contentType:undefined as string|undefined}}
  const {bucket}=s3Config();const h=await s3().send(new HeadObjectCommand({Bucket:bucket,Key:key}));
  return {size:Number(h.ContentLength||0),contentType:h.ContentType};
}
export async function getStorageRange(key:string,start?:number,end?:number){
  if(!isObjectStorage())return {body:(await import("node:stream")).Readable.toWeb(createReadStream(storagePath(key),start===undefined?undefined:{start,end})) as any,size:(await stat(storagePath(key))).size,contentType:undefined as string|undefined};
  const {bucket}=s3Config();const Range=start===undefined?undefined:`bytes=${start}-${end??""}`;
  const o=await s3().send(new GetObjectCommand({Bucket:bucket,Key:key,Range}));
  return {body:o.Body as any,size:Number(o.ContentLength||0),contentType:o.ContentType};
}
export function openStorage(key:string){return createReadStream(storagePath(key))}
