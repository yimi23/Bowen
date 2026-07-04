/**
 * Auto-label training images using Claude Vision
 */

import fs from 'fs';
import path from 'path';
import { anthropic } from '../lib/anthropic';

const TRAINING_DIR = path.join(__dirname, '../../training-data');
const IMAGES_DIR = path.join(TRAINING_DIR, 'images');
const LABELS_FILE = path.join(TRAINING_DIR, 'labels.json');

const CATEGORIES = [
  'pill-organizer-full',
  'pill-organizer-empty',
  'loose-pills',
  'human-face',
  'human-hand',
  'table-empty',
  'table-objects',
  'wall',
  'blur',
  'glare',
  'other',
];

const AUTO_LABEL_PROMPT = `Analyze this image and categorize it for GENI training data.

## CATEGORIES:

1. **pill-organizer-full** - Pill organizer with pills visible in compartments
2. **pill-organizer-empty** - Pill organizer with empty compartments (pills already taken)
3. **loose-pills** - Pills not in an organizer (on table, in hand, etc.)
4. **human-face** - Human face visible in frame
5. **human-hand** - Human hand visible (holding something, pointing, etc.)
6. **table-empty** - Empty table or surface with no objects
7. **table-objects** - Table with various objects (not pills)
8. **wall** - Wall or background, no objects of interest
9. **blur** - Blurry image, can't see clearly
10. **glare** - Glare or reflection blocking view
11. **other** - Something else not listed above

## YOUR TASK

Choose the MOST appropriate category for this image.

## RESPONSE FORMAT (JSON only)

{
  "category": "category-name",
  "confidence": 0.0-1.0,
  "description": "Brief description of what you see (1-2 sentences)",
  "alternative_category": "category-name" | null,
  "notes": "Any additional relevant details"
}

**Output ONLY the JSON, nothing else.**
`;

interface AutoLabelResult {
  category: string;
  confidence: number;
  description: string;
  alternative_category?: string | null;
  notes?: string;
}

async function analyzeImage(imagePath: string): Promise<AutoLabelResult> {
  const imageBuffer = fs.readFileSync(imagePath);
  const base64Image = imageBuffer.toString('base64');
  
  const ext = path.extname(imagePath).toLowerCase();
  const mediaType = ext === '.png' ? 'image/png' : 'image/jpeg';
  
  try {
    const message = await anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 512,
      system: 'You are an image classification system. Output ONLY valid JSON, no other text.',
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mediaType,
                data: base64Image,
              },
            },
            {
              type: 'text',
              text: AUTO_LABEL_PROMPT,
            },
          ],
        },
      ],
    });
    
    const responseText = message.content[0].type === 'text' ? message.content[0].text : '';
    
    // Extract JSON
    const jsonMatch = responseText.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('No JSON found in response');
    }
    
    const result: AutoLabelResult = JSON.parse(jsonMatch[0]);
    return result;
    
  } catch (error) {
    console.error(`❌ Error analyzing ${path.basename(imagePath)}:`, error);
    return {
      category: 'other',
      confidence: 0.0,
      description: 'Failed to analyze',
      notes: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function autoLabelImages() {
  console.log(`
╔════════════════════════════════════════╗
║                                        ║
║   🤖 Auto-Label Training Images       ║
║                                        ║
╚════════════════════════════════════════╝
  `);
  
  // Load existing labels
  let existingLabels: any[] = [];
  if (fs.existsSync(LABELS_FILE)) {
    existingLabels = JSON.parse(fs.readFileSync(LABELS_FILE, 'utf-8'));
    console.log(`📊 Found ${existingLabels.length} existing labels\n`);
  }
  
  // Get all images
  const files = fs.readdirSync(IMAGES_DIR).filter(f => 
    /\.(jpg|jpeg|png)$/i.test(f)
  );
  
  console.log(`📸 Found ${files.length} images to analyze\n`);
  
  const newLabels: any[] = [];
  const existingFilenames = new Set(existingLabels.map(l => l.filename));
  
  let analyzed = 0;
  let skipped = 0;
  
  for (const filename of files) {
    // Skip if already labeled
    if (existingFilenames.has(filename)) {
      console.log(`⏭️  ${filename} - already labeled, skipping`);
      skipped++;
      continue;
    }
    
    const imagePath = path.join(IMAGES_DIR, filename);
    
    console.log(`🔍 Analyzing: ${filename}`);
    
    const result = await analyzeImage(imagePath);
    
    console.log(`   Category: ${result.category} (${(result.confidence * 100).toFixed(0)}% confidence)`);
    console.log(`   Description: ${result.description}`);
    
    if (result.alternative_category) {
      console.log(`   Alternative: ${result.alternative_category}`);
    }
    
    const label = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      timestamp: Date.now(),
      category: result.category,
      description: result.description,
      filename: filename,
      confidence: result.confidence,
      auto_labeled: true,
      alternative_category: result.alternative_category,
      notes: result.notes,
    };
    
    newLabels.push(label);
    analyzed++;
    
    console.log(`   ✅ Labeled as: ${result.category}\n`);
    
    // Small delay to avoid rate limits
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  // Merge with existing labels
  const allLabels = [...existingLabels, ...newLabels];
  
  // Save labels
  fs.writeFileSync(LABELS_FILE, JSON.stringify(allLabels, null, 2));
  
  console.log('╔════════════════════════════════════════╗');
  console.log('║                                        ║');
  console.log('║   ✅ Auto-Labeling Complete!          ║');
  console.log('║                                        ║');
  console.log('╚════════════════════════════════════════╝\n');
  
  console.log(`📊 Results:`);
  console.log(`   Images analyzed: ${analyzed}`);
  console.log(`   Images skipped (already labeled): ${skipped}`);
  console.log(`   Total labeled images: ${allLabels.length}\n`);
  
  // Category breakdown
  const byCategory: Record<string, number> = {};
  allLabels.forEach(l => {
    byCategory[l.category] = (byCategory[l.category] || 0) + 1;
  });
  
  console.log('📊 By Category:');
  Object.entries(byCategory).sort((a, b) => b[1] - a[1]).forEach(([cat, count]) => {
    console.log(`   ${cat}: ${count} images`);
  });
  
  console.log(`\n📄 Labels saved to: ${LABELS_FILE}`);
  console.log('\n🎯 Next steps:');
  console.log('   1. Review labels.json to verify accuracy');
  console.log('   2. Run augmentation: npm run augment');
  console.log('   3. Prepare training data');
  console.log('   4. Train YOLO model in Google Colab\n');
}

// Run
if (require.main === module) {
  autoLabelImages().catch(console.error);
}

export { autoLabelImages };
