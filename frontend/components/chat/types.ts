import type { ChatResponse } from '@/lib/types';

export type Role = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  meta?: ChatResponse;
}

