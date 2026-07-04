import { Router, Request, Response } from 'express';
import { addActivity, state } from '../state';
import { emitActivity, emitIncomingMessage } from '../socket';
import { config } from '../config';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('twilio');

// GENI merge: these webhooks only ever BUILT TwiML XML — no API calls — so
// the twilio SDK import is replaced by two tiny XML helpers. Inbound
// webhooks stay here; outbound delivery lives in BOWEN's gate delivery layer.
const xmlEscape = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const messageTwiml = (text: string) =>
  `<?xml version="1.0" encoding="UTF-8"?><Response><Message>${xmlEscape(text)}</Message></Response>`;

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
    const patientFirstName = config.patient.name.split(' ')[0];
    res.type('text/xml');
    res.send(messageTwiml(`Thank you for your message. ${patientFirstName} will be notified. - GENI`));
    
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
    
    let body = '';
    if (CallStatus === 'ringing' || CallStatus === 'in-progress') {
      const first = config.patient.name.split(' ')[0];
      body =
        `<Say voice="Polly.Joanna">${xmlEscape(`This is GENI calling on behalf of ${config.patient.name}. Please check on ${first} immediately. They may need assistance.`)}</Say>` +
        '<Pause length="2"/>' +
        '<Say voice="Polly.Joanna">Press any key to confirm you received this alert.</Say>' +
        '<Gather numDigits="1" action="/api/twilio/webhook/voice/confirm"/>';
    }
    res.type('text/xml');
    res.send(`<?xml version="1.0" encoding="UTF-8"?><Response>${body}</Response>`);
    
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
  
  let body = '';
  if (Digits) {
    const first = config.patient.name.split(' ')[0];
    body = `<Say voice="Polly.Joanna">${xmlEscape(`Thank you for confirming. ${first} has been notified that help is on the way.`)}</Say>`;
    // Log confirmation
    addActivity('Emergency alert acknowledged by caregiver', 'system');
  }
  res.type('text/xml');
  res.send(`<?xml version="1.0" encoding="UTF-8"?><Response>${body}</Response>`);
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
