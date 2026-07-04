import { Server as SocketIOServer } from 'socket.io';
import { Server as HTTPServer } from 'http';
import { monitoring } from './services/monitoring/core';
import { config } from './config';
import { moduleLogger } from './lib/logger';

const log = moduleLogger('socket');

let io: SocketIOServer;

export function initializeSocket(httpServer: HTTPServer): SocketIOServer {
  io = new SocketIOServer(httpServer, {
    cors: {
      origin: config.security.corsOrigins,
      methods: ['GET', 'POST'],
    },
  });

  // Handshake auth — same shared secret as the REST API
  io.use((socket, next) => {
    if (!config.security.apiKey) return next();
    const token = socket.handshake.auth?.token;
    if (token === config.security.apiKey) return next();
    next(new Error('Unauthorized'));
  });

  io.on('connection', (socket) => {
    log.info({ detail: socket.id }, '✅ Client connected:');
    
    // Camera pause/resume events
    socket.on('pause-camera', () => {
      log.info('📷 Camera pause requested');
      monitoring.pause();
      socket.emit('camera-paused', { status: 'paused' });
    });
    
    socket.on('resume-camera', () => {
      log.info('📷 Camera resume requested');
      monitoring.resume();
      socket.emit('camera-resumed', { status: 'resumed' });
    });
    
    socket.on('disconnect', () => {
      log.info({ detail: socket.id }, '❌ Client disconnected:');
    });
  });
  
  return io;
}

export function getIO(): SocketIOServer {
  if (!io) {
    throw new Error('Socket.IO not initialized');
  }
  return io;
}

// Helper functions to emit events
export function emitActivity(activity: any) {
  if (io) {
    io.emit('activity', activity);
  }
}

export function emitMedicationUpdate(medication: any) {
  if (io) {
    io.emit('medication_update', medication);
  }
}

export function emitIncomingMessage(message: any) {
  if (io) {
    io.emit('incoming_message', message);
  }
}

export function emitSpeak(text: string) {
  if (io) {
    io.emit('speak', { text });
  }
}

export function emitFallDetected(data: Record<string, any> = {}) {
  if (io) {
    io.emit('fall_detected', data);
  }
}

export function emitFallAlert(data: {
  state: 'confirming' | 'emergency' | 'escalated' | 'cancelled';
  message: string;
  patient?: string;
  timestamp?: number;
  progress?: number;
  data?: any;
}) {
  if (io) {
    io.emit('fall_alert', data);
  }
}

export function emitHardwareStatus(status: any) {
  if (io) {
    io.emit('hardware_status', status);
  }
}

export function emitVisionUpdate(data: {
  timestamp: Date;
  observation: string;
  message?: string;
  concerns: string[];
}) {
  if (io) {
    io.emit('vision_update', data);
  }
}
