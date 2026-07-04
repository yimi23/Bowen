/**
 * Download public training datasets for GENI vision
 * Sources: Open Images, Kaggle, Roboflow Universe
 */

import fs from 'fs';
import path from 'path';
import https from 'https';

const DATASETS_DIR = path.join(__dirname, '../../training-data/downloaded');

// Public dataset URLs (pre-verified, safe to download)
const DATASETS = {
  // Roboflow Universe public datasets
  roboflow: [
    {
      name: 'pill-detection-v1',
      url: 'https://app.roboflow.com/ds/KtXoGvQUb0?key=YOUR_KEY',
      description: 'Pills and medication detection dataset',
      images: 500,
      note: 'Requires Roboflow account (free)',
    },
    {
      name: 'medication-organizer',
      url: 'https://universe.roboflow.com/medication-tracker/pill-organizer',
      description: 'Pill organizers in various conditions',
      images: 200,
      note: 'Public dataset',
    },
  ],
  
  // Sample datasets (direct download)
  samples: [
    {
      name: 'ejtech-candy-dataset',
      url: 'https://www.ejtech.io/candy_data.zip',
      description: 'Example YOLO dataset from the tutorial video',
      images: 150,
      format: 'YOLO',
    },
  ],
};

// Initialize download directory
function initDownloadDir() {
  if (!fs.existsSync(DATASETS_DIR)) {
    fs.mkdirSync(DATASETS_DIR, { recursive: true });
    console.log('✅ Created download directory');
  }
}

// Download file from URL
async function downloadFile(url: string, filename: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const filepath = path.join(DATASETS_DIR, filename);
    const file = fs.createWriteStream(filepath);
    
    https.get(url, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        // Follow redirect
        const redirectUrl = response.headers.location;
        if (redirectUrl) {
          return downloadFile(redirectUrl, filename).then(resolve).catch(reject);
        }
      }
      
      response.pipe(file);
      
      file.on('finish', () => {
        file.close();
        console.log(`✅ Downloaded: ${filename}`);
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(filepath, () => {});
      reject(err);
    });
  });
}

// Main function
async function downloadDatasets() {
  console.log(`
╔════════════════════════════════════════╗
║                                        ║
║   📥 GENI Dataset Downloader          ║
║                                        ║
╚════════════════════════════════════════╝
  `);
  
  initDownloadDir();
  
  console.log('\n📋 Available Datasets:\n');
  
  // List Roboflow datasets (manual download required)
  console.log('🌐 Roboflow Universe (manual download):');
  DATASETS.roboflow.forEach((ds, idx) => {
    console.log(`  ${idx + 1}. ${ds.name}`);
    console.log(`     Description: ${ds.description}`);
    console.log(`     Images: ~${ds.images}`);
    console.log(`     Note: ${ds.note}`);
    console.log('');
  });
  
  // Download sample datasets
  console.log('📦 Sample Datasets (auto-download):\n');
  for (const ds of DATASETS.samples) {
    console.log(`Downloading ${ds.name}...`);
    try {
      await downloadFile(ds.url, `${ds.name}.zip`);
      console.log(`   Images: ${ds.images}`);
      console.log(`   Format: ${ds.format}`);
    } catch (error) {
      console.error(`❌ Failed to download ${ds.name}:`, error);
    }
    console.log('');
  }
  
  console.log('\n✅ Downloads complete!');
  console.log(`📂 Location: ${DATASETS_DIR}`);
  console.log('\n💡 Next steps:');
  console.log('1. Extract downloaded zip files');
  console.log('2. Review images and relabel for pill detection');
  console.log('3. Merge with your existing training data');
  console.log('4. Run YOLO training when you have 100+ images');
}

// Run if called directly
if (require.main === module) {
  downloadDatasets().catch(console.error);
}

export { downloadDatasets, DATASETS };
