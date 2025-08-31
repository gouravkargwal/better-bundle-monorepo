import fs from 'fs';
import path from 'path';

const sourceEnvPath = path.join(process.cwd(), '..', 'local.env');
const targetEnvPath = path.join(process.cwd(), '.env');

try {
  // Read the source environment file
  const envContent = fs.readFileSync(sourceEnvPath, 'utf8');

  // Write to the target .env file
  fs.writeFileSync(targetEnvPath, envContent);

  console.log('✅ Environment variables copied successfully!');
  console.log(`📁 Source: ${sourceEnvPath}`);
  console.log(`📁 Target: ${targetEnvPath}`);

  // Display the scopes to confirm they're correct
  const lines = envContent.split('\n');
  const scopesLine = lines.find(line => line.startsWith('SHOPIFY_SCOPES='));
  if (scopesLine) {
    console.log(`🔧 Scopes found: ${scopesLine}`);
  }

} catch (error) {
  console.error('❌ Error copying environment variables:', error.message);
  process.exit(1);
}
