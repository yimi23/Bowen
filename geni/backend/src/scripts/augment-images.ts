/**
 * Image Augmentation Script for GENI Training Data
 * Multiplies existing 12 images into 120+ training images
 */

import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const TRAINING_DIR = path.join(__dirname, '../../training-data');
const IMAGES_DIR = path.join(TRAINING_DIR, 'images');
const AUGMENTED_DIR = path.join(TRAINING_DIR, 'augmented');
const LABELS_FILE = path.join(TRAINING_DIR, 'labels.json');

interface Label {
  id: string;
  timestamp: number;
  category: string;
  description: string;
  filename: string;
}

// Augmentation transforms
const AUGMENTATIONS = [
  { name: 'rotate-5', params: '-rotate 5' },
  { name: 'rotate-10', params: '-rotate 10' },
  { name: 'rotate-neg5', params: '-rotate -5' },
  { name: 'rotate-neg10', params: '-rotate -10' },
  { name: 'flip-h', params: '-flop' },
  { name: 'flip-v', params: '-flip' },
  { name: 'bright-20', params: '-modulate 120' },
  { name: 'bright-80', params: '-modulate 80' },
  { name: 'blur-1', params: '-blur 0x1' },
  { name: 'zoom-95', params: '-resize 95%' },
  { name: 'zoom-105', params: '-resize 105%' },
];

async function checkImageMagick(): Promise<boolean> {
  try {
    await execAsync('convert -version');
    return true;
  } catch {
    return false;
  }
}

async function augmentImage(
  inputPath: string,
  outputDir: string,
  baseName: string,
  transform: { name: string; params: string }
): Promise<string> {
  const outputName = `${baseName}-${transform.name}.jpg`;
  const outputPath = path.join(outputDir, outputName);
  
  await execAsync(`convert "${inputPath}" ${transform.params} "${outputPath}"`);
  
  return outputName;
}

async function augmentDataset() {
  console.log(`
╔════════════════════════════════════════╗
║                                        ║
║   🎨 GENI Image Augmentation          ║
║                                        ║
╚════════════════════════════════════════╝
  `);
  
  // Check ImageMagick
  console.log('🔍 Checking for ImageMagick...');
  const hasImageMagick = await checkImageMagick();
  
  if (!hasImageMagick) {
    console.error('❌ ImageMagick not found!');
    console.log('\n📦 Install with:');
    console.log('   brew install imagemagick\n');
    process.exit(1);
  }
  
  console.log('✅ ImageMagick found\n');
  
  // Create augmented directory
  if (!fs.existsSync(AUGMENTED_DIR)) {
    fs.mkdirSync(AUGMENTED_DIR, { recursive: true });
  }
  
  // Load labels
  const labels: Label[] = JSON.parse(fs.readFileSync(LABELS_FILE, 'utf-8'));
  console.log(`📊 Found ${labels.length} original images\n`);
  
  const newLabels: Label[] = [];
  let totalGenerated = 0;
  
  // Process each image
  for (const label of labels) {
    const inputPath = path.join(IMAGES_DIR, label.filename);
    
    if (!fs.existsSync(inputPath)) {
      console.warn(`⚠️  Skipping missing file: ${label.filename}`);
      continue;
    }
    
    const baseName = path.parse(label.filename).name;
    
    console.log(`🎨 Augmenting: ${label.filename}`);
    console.log(`   Category: ${label.category}`);
    
    // Copy original
    const originalCopy = `${baseName}-original.jpg`;
    fs.copyFileSync(inputPath, path.join(AUGMENTED_DIR, originalCopy));
    
    newLabels.push({
      ...label,
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      filename: originalCopy,
    });
    
    // Apply each augmentation
    for (const transform of AUGMENTATIONS) {
      try {
        const augmentedFilename = await augmentImage(
          inputPath,
          AUGMENTED_DIR,
          baseName,
          transform
        );
        
        newLabels.push({
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
          timestamp: Date.now(),
          category: label.category,
          description: `${label.description} (${transform.name})`,
          filename: augmentedFilename,
        });
        
        totalGenerated++;
      } catch (error) {
        console.error(`   ❌ Failed ${transform.name}:`, error);
      }
    }
    
    console.log(`   ✅ Generated ${AUGMENTATIONS.length} variations\n`);
  }
  
  // Save augmented labels
  const augmentedLabelsFile = path.join(AUGMENTED_DIR, 'labels.json');
  fs.writeFileSync(augmentedLabelsFile, JSON.stringify(newLabels, null, 2));
  
  console.log('╔════════════════════════════════════════╗');
  console.log('║                                        ║');
  console.log('║   ✅ Augmentation Complete!           ║');
  console.log('║                                        ║');
  console.log('╚════════════════════════════════════════╝\n');
  
  console.log(`📊 Results:`);
  console.log(`   Original images: ${labels.length}`);
  console.log(`   Augmented images: ${totalGenerated}`);
  console.log(`   Total images: ${newLabels.length}`);
  console.log(`   Multiplier: ${(newLabels.length / labels.length).toFixed(1)}x\n`);
  
  console.log(`📂 Output directory: ${AUGMENTED_DIR}`);
  console.log(`📄 Labels file: ${augmentedLabelsFile}\n`);
  
  // Category breakdown
  const byCategory: Record<string, number> = {};
  newLabels.forEach(l => {
    byCategory[l.category] = (byCategory[l.category] || 0) + 1;
  });
  
  console.log('📊 By Category:');
  Object.entries(byCategory).forEach(([cat, count]) => {
    console.log(`   ${cat}: ${count} images`);
  });
  
  console.log('\n🎯 Next steps:');
  console.log('   1. Review augmented images in augmented/');
  console.log('   2. Convert to YOLO format');
  console.log('   3. Train YOLO model in Google Colab');
  console.log('   4. Download trained model');
  console.log('   5. Integrate into GENI\n');
}

// Run
if (require.main === module) {
  augmentDataset().catch(console.error);
}

export { augmentDataset };
