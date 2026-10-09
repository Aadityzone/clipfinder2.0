import{requireUser}from"../../../../../lib/auth";import{db}from"../../../../../lib/db";
export async function PUT(req:Request,{params}:{params:Promise<{id:string}>}){try{const u=await requireUser();const{id}=await params;const b=await req.json();const clip=await db.clip.findFirst({where:{id},include:{project:true}});if(!clip||clip.project.userId!==u.id)return Response.json({error:"Not found"},{status:404});
 const raw=Array.isArray(b.segments)?b.segments:[{startS:b.startS,endS:b.endS}];const segments=raw.map((s:any)=>({startS:Number(s.startS),endS:Number(s.endS)})).filter((s:any)=>Number.isFinite(s.startS)&&Number.isFinite(s.endS)&&s.startS>=clip.startS&&s.endS>s.startS&&s.endS<=clip.endS);
 if(!segments.length)return Response.json({error:"Invalid edit segments"},{status:400});
 for(let i=1;i<segments.length;i++)if(segments[i].startS<segments[i-1].endS)return Response.json({error:"Segments cannot overlap"},{status:400});
 const aspect=["9:16","16:9","1:1"].includes(b.aspectRatio)?b.aspectRatio:"9:16";const first=segments[0];
 const edit=await db.clipEdit.upsert({where:{clipId:id},create:{clipId:id,aspectRatio:aspect,segments},update:{aspectRatio:aspect,segments,version:{increment:1}}});
 await db.clip.update({where:{id},data:{startS:first.startS,endS:segments[segments.length-1].endS,status:"EDITING"}});await db.creatorEvent.create({data:{userId:u.id,projectId:clip.projectId,event:"EDIT",metadata:{clipId:id,aspectRatio:aspect,segmentCount:segments.length,editVersion:edit.version}}});return Response.json(edit)
 }catch(e){if(e instanceof Error&&e.message==="UNAUTHENTICATED")return Response.json({error:"Unauthorized"},{status:401});throw e}}
