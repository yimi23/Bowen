export interface Activity {
  id: string;
  time: string;
  message: string;
  type: 'medication' | 'message' | 'voice' | 'movement' | 'reminder' | 'emergency' | 'system';
  timestamp: number;
}

export function createActivity(
  message: string,
  type: Activity['type']
): Activity {
  const now = new Date();
  return {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    time: now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }),
    message,
    type,
    timestamp: Date.now(),
  };
}
