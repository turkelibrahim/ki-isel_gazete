import { useEffect, useState } from "react";
import { adminRequest } from "../services/adminApi";
export function useFeedbackStats(){ const [data,setData]=useState<any>(); useEffect(()=>{adminRequest("/api/admin/stats/feedback").then(setData);},[]); return data;}
