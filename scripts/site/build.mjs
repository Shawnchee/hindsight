/** Assemble only approved public files; never copy the repository tree. */
import { cp, mkdir, mkdtemp, readFile, rename, rm, lstat, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../../', import.meta.url));
const destination = join(root, 'site-dist');
const marker = '.hindsight-site-build';
const assets = ['index.html', 'styles.css', 'app.js', 'assets/favicon.svg',
  'assets/fonts/InterVariable.woff2', 'assets/fonts/OFL.txt', 'data/research-preview.json', 'data/DeFiHackLabs-LICENSE.txt', 'data/Hindsight-LICENSE.txt'];

async function regular(path) {
  const stat = await lstat(path);
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('Expected a regular public asset');
}

try {
  if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('Node 22 or later is required');
  let existing;
  try { existing = await lstat(destination); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (existing) {
    if (!existing.isDirectory() || existing.isSymbolicLink()) {
      throw new Error('Refusing to replace an unrecognized site-dist directory');
    }
    await regular(join(destination, marker));
    if (await readFile(join(destination, marker), 'utf8') !== 'hindsight-public-site-v1\n') {
      throw new Error('Refusing to replace an unrecognized site-dist directory');
    }
  }
  const preview = spawnSync('python3', ['-I', join(root, 'scripts/site/research_preview.py')], { cwd: root, stdio: 'inherit' });
  if (preview.status !== 0) throw new Error('Dataset preview validation failed');
  const cli = join(root, 'docs/node_modules/vitepress/bin/vitepress.js');
  await regular(cli);
  const result = spawnSync(process.execPath, [cli, 'build', '.'], { cwd: join(root, 'docs'), stdio: 'inherit' });
  if (result.status !== 0) throw new Error('Documentation build failed');
  const stage = await mkdtemp(join(root, 'site-dist.stage-'));
  try {
    for (const asset of assets) {
      const source = join(root, 'website', asset);
      await regular(source);
      await mkdir(dirname(join(stage, asset)), { recursive: true });
      await cp(source, join(stage, asset));
    }
    await cp(join(root, 'docs/.vitepress/dist'), join(stage, 'docs'), { recursive: true, dereference: false });
    await writeFile(join(stage, marker), 'hindsight-public-site-v1\n');
    const checks = spawnSync('python3', ['-I', join(root, 'scripts/site/check.py'), '--root', stage], { cwd: root, stdio: 'inherit' });
    if (checks.status !== 0) throw new Error('Public artifact checks failed');
    await rm(destination, { recursive: true, force: true });
    await rename(stage, destination);
  } finally { await rm(stage, { recursive: true, force: true }); }
  console.log('Public site assembled in site-dist/. No upload or deployment performed.');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
