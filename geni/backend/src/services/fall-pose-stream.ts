import { spawn, ChildProcessWithoutNullStreams } from 'child_process';
import path from 'path';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('fall-pose-stream');

interface FallPoseResult {
  id: string;
  timestamp: number;
  keypointsDetected: boolean;
  noseY?: number;
  hipY?: number;
  shoulderY?: number;
  noseVelocity?: number;
  hipVelocity?: number;
  personDown: boolean;
  fallPrimed: boolean;
  emergencyTriggered: boolean;
  stillSeconds: number;
  confirmationTime: number;
  message?: string;
}

class FallPoseStream {
  private process: ChildProcessWithoutNullStreams | null = null;
  private pending = new Map<string, (result: FallPoseResult) => void>();
  private stderrBuffer = '';
  private isStarting = false;
  
  private readonly scriptPath = path.join(__dirname, '../../scripts/fall_pose_stream.py');
  private readonly requestTimeoutMs = 45000;
  
  private ensureProcess() {
    if (this.process || this.isStarting) return;
    this.isStarting = true;
    
    this.process = spawn('python3', [this.scriptPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    
    this.process.stdout.setEncoding('utf-8');
    this.process.stdout.on('data', (data: string) => {
      const lines = data.split('\n').filter(line => line.trim());
      for (const line of lines) {
        try {
          const result = JSON.parse(line) as FallPoseResult;
          const resolver = this.pending.get(result.id);
          if (resolver) {
            this.pending.delete(result.id);
            resolver(result);
          }
        } catch (error) {
          log.error({ err: error }, '❌ Fall pose stream parse error:');
        }
      }
    });
    
    this.process.stderr.setEncoding('utf-8');
    this.process.stderr.on('data', (data: string) => {
      this.stderrBuffer += data;
      if (this.stderrBuffer.length > 5000) {
        this.stderrBuffer = this.stderrBuffer.slice(-2000);
      }
      log.error({ stderr: data.trim() }, 'fall pose stream stderr');
    });
    
    this.process.on('exit', () => {
      this.process = null;
      this.isStarting = false;
    });
    
    this.isStarting = false;
  }
  
  async analyzeFrame(imageBase64: string): Promise<FallPoseResult | null> {
    this.ensureProcess();
    if (!this.process) {
      return null;
    }
    
    const id = `fall-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    
    const payload = JSON.stringify({
      id,
      image: imageBase64,
    });
    
    const resultPromise = new Promise<FallPoseResult>((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('Fall pose analysis timeout'));
      }, this.requestTimeoutMs);
      
      this.pending.set(id, (result) => {
        clearTimeout(timeout);
        resolve(result);
      });
    });
    
    this.process.stdin.write(payload + '\n');
    
    try {
      return await resultPromise;
    } catch (error) {
      log.error({ err: error }, '❌ Fall pose analysis failed:');
      return null;
    }
  }
}

export const fallPoseStream = new FallPoseStream();
