import { useEffect, useState } from "react";
import { adminRequest } from "../services/adminApi";
export function useReclassificationQueue(){ const [data,setData]=useState<any[]>([]); useEffect(()=>{adminRequest("/api/admin/reclassify/queue").then((r)=>setData(r.queue||[]));},[]); return data;}
