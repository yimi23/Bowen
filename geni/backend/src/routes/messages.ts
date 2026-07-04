import { Router, Request, Response } from 'express';
import { sendWhatsAppMessage } from '../services/twilio';
import { state, addActivity, getPrimaryContact } from '../state';
import { emitActivity } from '../socket';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('messages');

const router = Router();

router.post('/send-message', async (req: Request, res: Response) => {
  try {
    const { to, message, contactName } = req.body;
    
    if (!message) {
      return res.status(400).json({ error: 'Message is required' });
    }
    
    // Determine recipient
    let recipientPhone = to;
    let recipientName = contactName;
    
    if (!recipientPhone) {
      // Default to primary contact
      const primaryContact = getPrimaryContact();
      if (primaryContact) {
        recipientPhone = primaryContact.phone;
        recipientName = primaryContact.name;
      } else {
        return res.status(400).json({ error: 'No recipient specified and no primary contact found' });
      }
    }
    
    // Send WhatsApp message
    const success = await sendWhatsAppMessage(recipientPhone, message);
    
    if (success) {
      const activity = addActivity(
        `Message sent to ${recipientName || recipientPhone}: "${message}"`,
        'message'
      );
      emitActivity(activity);
      
      res.json({ success: true, recipient: recipientName || recipientPhone });
    } else {
      res.status(500).json({ error: 'Failed to send message' });
    }
    
  } catch (error) {
    log.error({ err: error }, '❌ Send message error:');
    res.status(500).json({ error: 'Failed to send message' });
  }
});

export default router;
