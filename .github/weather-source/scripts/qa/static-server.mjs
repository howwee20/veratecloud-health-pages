// A deliberately plain static file server for QA: no rewrites, no fallbacks.
// If a route works here it works on ordinary static hosting. Responses carry
// the headers from deploy/security-headers.json so tests exercise the real CSP.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const headers = JSON.parse(fs.readFileSync(path.join(ROOT, 'deploy', 'security-headers.json'), 'utf8')).all;

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.gif': 'image/gif', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.csv': 'text/csv; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.ico': 'image/x-icon', '.xml': 'application/xml',
};

export function startServer({ dir = path.resolve(ROOT, process.env.DIST_DIR ?? 'dist'), port = 0 } = {}) {
  const server = http.createServer((req, res) => {
    const send = (status, file, extra = {}) => {
      const ext = path.extname(file);
      // Raw logger files have no extension; serve them as plain text.
      const type = TYPES[ext] ?? (ext === '' ? 'text/plain; charset=utf-8' : 'application/octet-stream');
      res.writeHead(status, { 'Content-Type': type, ...headers, ...extra });
      if (req.method === 'HEAD') res.end();
      else fs.createReadStream(file).pipe(res);
    };
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      res.writeHead(405, { Allow: 'GET, HEAD', ...headers });
      return res.end();
    }
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    } catch {
      res.writeHead(400, headers);
      return res.end();
    }
    const target = path.normalize(path.join(dir, pathname));
    if (!target.startsWith(dir)) {
      res.writeHead(403, headers);
      return res.end();
    }
    fs.stat(target, (err, stat) => {
      if (!err && stat.isDirectory()) {
        if (!pathname.endsWith('/')) {
          res.writeHead(301, { Location: `${pathname}/`, ...headers });
          return res.end();
        }
        const index = path.join(target, 'index.html');
        return fs.existsSync(index) ? send(200, index) : notFound();
      }
      if (!err && stat.isFile()) return send(200, target);
      return notFound();
    });
    function notFound() {
      const page = path.join(dir, '404.html');
      if (fs.existsSync(page)) return send(404, page);
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8', ...headers });
      res.end('Not found');
    }
  });
  return new Promise((resolve) => {
    server.listen(port, '127.0.0.1', () => {
      const url = `http://127.0.0.1:${server.address().port}`;
      resolve({ url, close: () => new Promise((done) => server.close(done)) });
    });
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { url } = await startServer({ port: Number(process.env.PORT ?? 4321) });
  console.log(`Serving dist/ at ${url}`);
}
