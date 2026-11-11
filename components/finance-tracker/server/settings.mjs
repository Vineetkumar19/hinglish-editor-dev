import {z} from 'zod';
export const settingsSchema=z.object({widgets:z.array(z.enum(['history','news','allocation','income','due','holdings'])).max(6).optional(),classifications:z.array(z.string().trim().min(1).max(60)).max(20).optional(),benchmark:z.string().regex(/^[\w.^=\-]{1,40}$/).optional(),model:z.string().min(1).max(150).optional(),autoRefresh:z.boolean().optional()}).strict();
