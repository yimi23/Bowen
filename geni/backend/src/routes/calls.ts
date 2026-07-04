import { Router, Request, Response } from 'express';
import { makeVoiceCall, callDoctor } from '../services/twilio';
import { state, addActivity } from '../state';
import { emitActivity } from '../socket';
import { config } from '../config';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('calls');

const router = Router();

/**
 * Call caregiver
 */
router.post('/call/caregiver', async (req: Request, res: Response) => {
  try {
    const { contactId, reason } = req.body;
    
    // Find contact
    const contact = state.contacts.find(c => c.name === contactId || c.phone === contactId);
    
    if (!contact) {
      return res.status(404).json({ error: 'Contact not found' });
    }
    
    const message = reason || `${config.patient.name} needs to speak with you. Please call back when possible.`;
    
    // Make the call
    const success = await makeVoiceCall(contact.phone, message, 'GENI');
    
    if (success) {
      const activity = addActivity(
        `Calling ${contact.name} (${contact.relationship})`,
        'system'
      );
      emitActivity(activity);
      
      res.json({ 
        success: true, 
        message: `Calling ${contact.name} at ${contact.phone}` 
      });
    } else {
      res.status(500).json({ error: 'Failed to initiate call' });
    }
    
  } catch (error) {
    log.error({ err: error }, '❌ Call caregiver error:');
    res.status(500).json({ error: 'Failed to call caregiver' });
  }
});

/**
 * Call doctor
 */
router.post('/call/doctor', async (req: Request, res: Response) => {
  try {
    const { doctorName, reason } = req.body;
    
    // In real system, would look up doctor in database
    // For demo, using hardcoded Dr. Smith
    const doctorPhone = '+15559876543'; // Dr. Smith's number from UI
    
    const message = reason || `${state.patient.name} needs to schedule an appointment or discuss a concern.`;
    
    const success = await callDoctor(doctorPhone, state.patient.name, message);
    
    if (success) {
      const activity = addActivity(
        `Calling Dr. ${doctorName || 'Smith'} (Primary Care)`,
        'system'
      );
      emitActivity(activity);
      
      res.json({ 
        success: true, 
        message: `Calling Dr. ${doctorName || 'Smith'}` 
      });
    } else {
      res.status(500).json({ error: 'Failed to call doctor' });
    }
    
  } catch (error) {
    log.error({ err: error }, '❌ Call doctor error:');
    res.status(500).json({ error: 'Failed to call doctor' });
  }
});

/**
 * Emergency call - calls all contacts
 */
router.post('/call/emergency', async (req: Request, res: Response) => {
  try {
    const { reason } = req.body;
    
    const emergencyMessage = reason || `Emergency alert triggered. Please check on ${config.patient.name} immediately.`;
    
    // Call all primary contacts
    const primaryContacts = state.contacts.filter(c => c.isPrimary);
    
    for (const contact of primaryContacts) {
      await makeVoiceCall(contact.phone, emergencyMessage, 'GENI Emergency');
    }
    
    const activity = addActivity(
      `Emergency calls initiated to ${primaryContacts.length} contact(s)`,
      'emergency'
    );
    emitActivity(activity);
    
    res.json({ 
      success: true, 
      message: `Called ${primaryContacts.length} emergency contacts`,
      contacts: primaryContacts.map(c => c.name)
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Emergency call error:');
    res.status(500).json({ error: 'Failed to make emergency calls' });
  }
});

export default router;
