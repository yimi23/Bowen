import { Router, Request, Response } from 'express';
import twilio from 'twilio';
import { addActivity, state } from '../state';
import { emitActivity, emitIncomingMessage } from '../socket';
import { config } from '../config';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('twilio');

const MessagingResponse = twilio.twiml.MessagingResponse;
const VoiceResponse = twilio.twiml.VoiceResponse;

const router = Router();

/**
 * Webhook for incoming WhatsApp/SMS messages
 * Twilio will POST here when caregiver responds
 */
router.post('/webhook/message', (req: Request, res: Response) => {
  try {
    const { From, Body, ProfileName } = req.body;
    
    log.info(`📨 Incoming message from ${From} (${ProfileName}): ${Body}`);
    
    // Parse sender info
    const senderPhone = From.replace('whatsapp:', '');
    const senderName = ProfileName || senderPhone;
    
    // Find contact in our system
    const contact = state.contacts.find(c => c.phone === senderPhone);
    const contactName = contact?.name || senderName;
    const relationship = contact?.relationship || 'Contact';
    
    // Log activity
    const activity = addActivity(
      `Message from ${contactName} (${relationship})`,
      'message'
    );
    emitActivity(activity);
    
    // Emit incoming message to frontend (real-time)
    emitIncomingMessage({
      from: contactName,
      relationship: relationship,
      phone: senderPhone,
      message: Body,
      timestamp: Date.now(),
    });
    
    // Auto-respond (optional)
    const twiml = new MessagingResponse();
    const patientFirstName = config.patient.name.split(' ')[0];
    twiml.message(`Thank you for your message. ${patientFirstName} will be notified. - GENI`);
    
    res.type('text/xml');
    res.send(twiml.toString());
    
  } catch (error) {
    log.error({ err: error }, '❌ Webhook error:');
    res.status(500).send('Error processing message');
  }
});

/**
 * Webhook for incoming voice calls
 * Handle callbacks when someone answers emergency call
 */
router.post('/webhook/voice', (req: Request, res: Response) => {
  try {
    const { From, CallStatus } = req.body;
    
    log.info(`📞 Voice call status from ${From}: ${CallStatus}`);
    
    const twiml = new VoiceResponse();
    
    if (CallStatus === 'ringing' || CallStatus === 'in-progress') {
      // Call connected - play emergency message
      twiml.say({
        voice: 'Polly.Joanna'
      }, `This is GENI calling on behalf of ${config.patient.name}. Please check on ${config.patient.name.split(' ')[0]} immediately. They may need assistance.`);
      
      twiml.pause({ length: 2 });
      
      twiml.say({
        voice: 'Polly.Joanna'
      }, 'Press any key to confirm you received this alert.');
      
      // Gather response
      twiml.gather({
        numDigits: 1,
        action: '/api/twilio/webhook/voice/confirm',
      });
    }
    
    res.type('text/xml');
    res.send(twiml.toString());
    
  } catch (error) {
    log.error({ err: error }, '❌ Voice webhook error:');
    res.status(500).send('Error');
  }
});

/**
 * Voice call confirmation
 */
router.post('/webhook/voice/confirm', (req: Request, res: Response) => {
  const { Digits } = req.body;
  
  const twiml = new VoiceResponse();
  
  if (Digits) {
    twiml.say({
      voice: 'Polly.Joanna'
    }, `Thank you for confirming. ${config.patient.name.split(' ')[0]} has been notified that help is on the way.`);
    
    // Log confirmation
    addActivity('Emergency alert acknowledged by caregiver', 'system');
  }
  
  res.type('text/xml');
  res.send(twiml.toString());
});

/**
 * Status callback for call/message delivery
 */
router.post('/webhook/status', (req: Request, res: Response) => {
  const { MessageStatus, CallStatus, To } = req.body;
  
  log.info({ to: To, status: MessageStatus || CallStatus }, 'delivery status update');
  
  res.sendStatus(200);
});

export default router;
