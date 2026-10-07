import {createReadStream,createWriteStream} from "node:fs";import {mkdir} from "node:fs/promises";import path from "node:path";
export function storageRoot(){return path.resolve(process.env.MEDIA_STORAGE_ROOT||"../storage")}
export async function ensureStorage(){await mkdir(storageRoot(),{recursive:true})}
export function storagePath(key:string){return path.join(storageRoot(),key.replace(/^[/\\]+/,""))}
export async function saveStream(key:string,stream:NodeJS.ReadableStream){await ensureStorage();const target=storagePath(key);await mkdir(path.dirname(target),{recursive:true});return new Promise<string>((resolve,reject)=>{const out=createWriteStream(target);stream.pipe(out);out.on("finish",()=>resolve(target));out.on("error",reject);stream.on("error",reject)})}
export function openStorage(key:string){return createReadStream(storagePath(key))}