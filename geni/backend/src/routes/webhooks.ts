import { Router, Request, Response } from 'express';
import { addActivity } from '../state';
import { emitActivity, emitIncomingMessage } from '../socket';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('webhooks');

const router = Router();

// Twilio WhatsApp webhook
router.post('/webhook/twilio', async (req: Request, res: Response) => {
  try {
    const { From, Body, ProfileName } = req.body;
    
    log.info({ from: From, profileName: ProfileName }, 'incoming WhatsApp message');
    
    // Parse phone number
    const fromNumber = From.replace('whatsapp:', '');
    
    // Log incoming message
    const activity = addActivity(
      `Message from ${ProfileName || fromNumber}: "${Body}"`,
      'message'
    );
    emitActivity(activity);
    
    // Emit to frontend for banner display
    emitIncomingMessage({
      from: fromNumber,
      senderName: ProfileName || 'Unknown',
      message: Body,
      timestamp: Date.now(),
    });
    
    // Respond to Twilio (empty response = no auto-reply)
    res.type('text/xml');
    res.send('<Response></Response>');
    
  } catch (error) {
    log.error({ err: error }, '❌ Webhook error:');
    res.status(500).send('<Response></Response>');
  }
});

export default router;
