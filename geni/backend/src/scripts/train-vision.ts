/**
 * GENI Vision Training Script
 * Capture and label objects for improved recognition
 */

import fs from 'fs';
import path from 'path';
import readline from 'readline';

const TRAINING_DIR = path.join(__dirname, '../../training-data');
const IMAGES_DIR = path.join(TRAINING_DIR, 'images');
const LABELS_FILE = path.join(TRAINING_DIR, 'labels.json');

// Object categories
const CATEGORIES = {
  'pill-organizer-full': 'Pill organizer with pills visible',
  'pill-organizer-empty': 'Pill organizer with empty compartments',
  'loose-pills': 'Pills not in organizer',
  'human-face': 'Human face in frame',
  'human-hand': 'Human hand in frame',
  'table-empty': 'Empty table surface',
  'table-objects': 'Table with random objects',
  'wall': 'Wall or background',
  'blur': 'Blurry/unclear image',
  'glare': 'Glare or reflection blocking view',
  'other': 'Other object not listed',
};

interface TrainingLabel {
  id: string;
  timestamp: number;
  category: string;
  description: string;
  filename: string;
}

// Initialize training directory
function initTrainingDir() {
  if (!fs.existsSync(TRAINING_DIR)) {
    fs.mkdirSync(TRAINING_DIR, { recursive: true });
    console.log('✅ Created training data directory');
  }
  
  if (!fs.existsSync(IMAGES_DIR)) {
    fs.mkdirSync(IMAGES_DIR, { recursive: true });
    console.log('✅ Created images directory');
  }
  
  if (!fs.existsSync(LABELS_FILE)) {
    fs.writeFileSync(LABELS_FILE, JSON.stringify([], null, 2));
    console.log('✅ Created labels file');
  }
}

// Load existing labels
function loadLabels(): TrainingLabel[] {
  const data = fs.readFileSync(LABELS_FILE, 'utf-8');
  return JSON.parse(data);
}

// Save labels
function saveLabels(labels: TrainingLabel[]) {
  fs.writeFileSync(LABELS_FILE, JSON.stringify(labels, null, 2));
}

// Save training image
function saveTrainingImage(base64Data: string, label: TrainingLabel): string {
  // Remove data URL prefix if present
  const cleanBase64 = base64Data.replace(/^data:image\/\w+;base64,/, '');
  const buffer = Buffer.from(cleanBase64, 'base64');
  
  const filename = `${label.id}.jpg`;
  const filepath = path.join(IMAGES_DIR, filename);
  
  fs.writeFileSync(filepath, buffer);
  return filename;
}

// Interactive labeling
async function labelImage(base64Data: string) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  
  console.log('\n📸 New image captured!\n');
  console.log('Available categories:');
  Object.entries(CATEGORIES).forEach(([key, desc], idx) => {
    console.log(`  ${idx + 1}. ${key} - ${desc}`);
  });
  
  return new Promise<TrainingLabel | null>((resolve) => {
    rl.question('\nSelect category (1-11) or "skip": ', (answer) => {
      if (answer.toLowerCase() === 'skip') {
        console.log('⏭️  Skipped');
        rl.close();
        resolve(null);
        return;
      }
      
      const categoryIndex = parseInt(answer) - 1;
      const categoryKeys = Object.keys(CATEGORIES);
      
      if (categoryIndex < 0 || categoryIndex >= categoryKeys.length) {
        console.log('❌ Invalid category');
        rl.close();
        resolve(null);
        return;
      }
      
      const category = categoryKeys[categoryIndex];
      
      rl.question('Add description (optional): ', (description) => {
        const label: TrainingLabel = {
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
          timestamp: Date.now(),
          category,
          description: description || CATEGORIES[category as keyof typeof CATEGORIES],
          filename: '',
        };
        
        console.log('✅ Image labeled as:', category);
        rl.close();
        resolve(label);
      });
    });
  });
}

// Main training loop
async function trainVision() {
  console.log(`
╔════════════════════════════════════════╗
║                                        ║
║   📸 GENI Vision Training Mode        ║
║                                        ║
║   Show objects to the camera and      ║
║   label them to improve recognition   ║
║                                        ║
╚════════════════════════════════════════╝
  `);
  
  initTrainingDir();
  
  const labels = loadLabels();
  console.log(`\n📊 Current dataset: ${labels.length} labeled images\n`);
  
  console.log('Instructions:');
  console.log('1. Open GENI frontend at http://localhost:3000');
  console.log('2. Use the camera to capture images');
  console.log('3. Come back here to label each image');
  console.log('4. Press Ctrl+C when done\n');
  
  console.log('⚠️  Note: This is a manual training script.');
  console.log('Use the /api/training endpoint to submit images from frontend.\n');
}

// Export training route (to be used in backend)
export async function saveTrainingData(
  imageBase64: string,
  category: string,
  description?: string
): Promise<{ success: boolean; id: string }> {
  initTrainingDir();
  
  const labels = loadLabels();
  
  const label: TrainingLabel = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
    timestamp: Date.now(),
    category,
    description: description || CATEGORIES[category as keyof typeof CATEGORIES] || category,
    filename: '',
  };
  
  label.filename = saveTrainingImage(imageBase64, label);
  
  labels.push(label);
  saveLabels(labels);
  
  console.log(`✅ Training image saved: ${label.category} (${label.id})`);
  
  return { success: true, id: label.id };
}

// Export for use in routes
export { CATEGORIES, TrainingLabel };

// CLI mode
if (require.main === module) {
  trainVision();
}
