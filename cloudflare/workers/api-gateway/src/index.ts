export interface Env {
  NEXORUM_KV: KVNamespace;
  API_BASE_URL: string;
}

// Rate limiting via Cloudflare KV
async function checkRateLimit(request: Request, kv: KVNamespace): Promise<boolean> {
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  const key = `rate:${ip}`;
  const now = Math.floor(Date.now() / 1000);
  const windowStart = Math.floor(now / 60) * 60;
  const countKey = `${key}:${windowStart}`;

  const current = await kv.get(countKey);
  const count = current ? parseInt(current) : 0;

  if (count > 100) return false; // 100 req/min

  await kv.put(countKey, String(count + 1), { expirationTtl: 120 });
  return true;
}

// JWT validation (simplified — use jose library in production)
async function validateToken(token: string): Promise<{sub: string; role: string} | null> {
  try {
    const [header, payload, signature] = token.split('.');
    const decoded = JSON.parse(atob(payload));
    if (decoded.exp * 1000 < Date.now()) return null;
    return { sub: decoded.sub, role: decoded.role };
  } catch {
    return null;
  }
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
          'Access-Control-Allow-Headers': 'Authorization, Content-Type',
          'Access-Control-Max-Age': '86400',
        }
      });
    }

    // Rate limiting
    const allowed = await checkRateLimit(request, env.NEXORUM_KV);
    if (!allowed) {
      return new Response(JSON.stringify({error: "Rate limit exceeded"}), {
        status: 429,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Auth check for protected routes
    const publicPaths = ['/api/v1/auth/login', '/api/v1/auth/register', '/api/v1/auth/refresh'];
    const isPublic = publicPaths.some(p => url.pathname.startsWith(p));

    if (!isPublic) {
      const authHeader = request.headers.get('Authorization');
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return new Response(JSON.stringify({error: "Unauthorized"}), {
          status: 401,
          headers: { 'Content-Type': 'application/json' }
        });
      }
      const token = authHeader.slice(7);
      const user = await validateToken(token);
      if (!user) {
        return new Response(JSON.stringify({error: "Invalid token"}), {
          status: 401,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }

    // Route to backend services
    let targetUrl: string;
    if (url.pathname.startsWith('/api/v1/ai/')) {
      targetUrl = `${env.API_BASE_URL}/api/v1/ai${url.pathname.slice(10)}${url.search}`;
    } else if (url.pathname.startsWith('/api/v1/exchange/')) {
      targetUrl = `${env.API_BASE_URL}/api/v1/exchange${url.pathname.slice(16)}${url.search}`;
    } else if (url.pathname.startsWith('/api/v1/risk/')) {
      targetUrl = `${env.API_BASE_URL}/api/v1/risk${url.pathname.slice(13)}${url.search}`;
    } else if (url.pathname.startsWith('/api/v1/auth/')) {
      targetUrl = `${env.API_BASE_URL}/api/v1/auth${url.pathname.slice(13)}${url.search}`;
    } else if (url.pathname.startsWith('/api/v1/market/')) {
      targetUrl = `${env.API_BASE_URL}/api/v1/market${url.pathname.slice(15)}${url.search}`;
    } else {
      return new Response(JSON.stringify({error: "Not found"}), {
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Forward request
    const modifiedRequest = new Request(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });

    const response = await fetch(modifiedRequest);
    const newHeaders = new Headers(response.headers);
    newHeaders.set('Access-Control-Allow-Origin', '*');

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  }
};
