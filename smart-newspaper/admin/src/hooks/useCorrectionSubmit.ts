import { adminRequest } from "../services/adminApi";
export function useCorrectionSubmit(){ return (article_id:string, corrected_labels:string[], correction_reason?:string)=>adminRequest("/api/admin/reclassify",{method:"POST", body:JSON.stringify({article_id, corrected_labels, correction_reason})});}
