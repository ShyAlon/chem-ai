import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';

function appShell() {
  return {
    name: 'homechem-app-shell',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const template = readFileSync(new URL('./service-worker.js', import.meta.url), 'utf8');
      const assets = Object.keys(bundle).filter(name => name.startsWith('assets/')).sort();
      const files = ['icon.svg', 'icon-192.png', 'icon-512.png', 'manifest.webmanifest'];
      const shell = ['/', ...files.concat(assets).map(name => '/' + name)];
      const hash = createHash('sha256').update(template).update(JSON.stringify(shell));
      hash.update(bundle['index.html'].source);
      for (const file of files) {
        hash.update(readFileSync(new URL('./public/' + file, import.meta.url)));
      }
      const id = hash.digest('hex').slice(0, 16);
      this.emitFile({
        type: 'asset', fileName: 'sw.js',
        source: template.replace('__BUILD_ID__', JSON.stringify(id)).replace('__APP_SHELL__', JSON.stringify(shell)),
      });
    },
  };
}

export default defineConfig({
  plugins: [appShell()],
  server: { proxy: { '/api': process.env.HOMECHEM_API_URL || 'http://127.0.0.1:8000' } },
});
