import { Router, Request, Response } from 'express';
import { state } from '../state';

const router = Router();

router.get('/status', (req: Request, res: Response) => {
  res.json({
    patient: state.patient,
    contacts: state.contacts,
    medications: state.todaysMedications,
    activities: state.activities.slice(0, 10), // Last 10 activities
    reminders: state.reminders,
    hardware: state.hardwareStatus,
    pillCheckResults: state.pillCheckResults.slice(-5), // Last 5 pill checks
    familyMessages: state.familyMessages.slice(-10), // Last 10 messages
  });
});

export default router;
