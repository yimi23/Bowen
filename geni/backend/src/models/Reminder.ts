export interface Reminder {
  id: string;
  time: string;
  message: string;
  completed: boolean;
  type: 'medication' | 'appointment' | 'call' | 'general';
}
