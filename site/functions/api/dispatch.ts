interface Env {
  GITHUB_TOKEN: string;
  ALLOWED_REPO?: string;
}

const JSON_HEADERS = {
  'content-type': 'application/json',
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'POST, OPTIONS',
  'access-control-allow-headers': 'content-type',
};

const sanitizeSlug = (input: string): string =>
  input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);

const timestampPrefix = (): string => {
  const d = new Date();
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mi = String(d.getUTCMinutes()).padStart(2, '0');
  const ss = String(d.getUTCSeconds()).padStart(2, '0');
  return `${yyyy}${mm}${dd}-${hh}${mi}${ss}`;
};

export const onRequestOptions = async () => {
  return new Response(null, { status: 204, headers: JSON_HEADERS });
};

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  try {
    if (!env.GITHUB_TOKEN) {
      return new Response(JSON.stringify({ error: 'Missing server secret GITHUB_TOKEN' }), {
        status: 500,
        headers: JSON_HEADERS,
      });
    }

    const body = await request.json<any>();
    const repo = String(body.repo || '').trim() || 'bryanwhiting/weatherman';
    const allowedRepo = env.ALLOWED_REPO || 'bryanwhiting/weatherman';
    if (repo !== allowedRepo) {
      return new Response(JSON.stringify({ error: `Repo not allowed. Expected ${allowedRepo}` }), {
        status: 403,
        headers: JSON_HEADERS,
      });
    }

    const payloadObj = typeof body.payload === 'string' ? JSON.parse(body.payload || '{}') : (body.payload || {});
    const runNameRaw = String(body.run_name_root || payloadObj.run_name_root || '').trim();
    if (!runNameRaw) {
      return new Response(JSON.stringify({ error: 'payload.run_name_root is required' }), {
        status: 400,
        headers: JSON_HEADERS,
      });
    }

    const useM5 = Boolean(body.use_m5);
    const nSeries = Number(payloadObj.n_series ?? 3);
    if (useM5) {
      payloadObj.series_name = 'demo_mode_m5';
    } else if (String(payloadObj.series_name || '').trim() === 'demo_mode_m5') {
      return new Response(JSON.stringify({ error: 'series_name "demo_mode_m5" is reserved for demo mode' }), {
        status: 400,
        headers: JSON_HEADERS,
      });
    }

    const cleanName = sanitizeSlug(runNameRaw) || 'forecast';
    const slug = `${timestampPrefix()}-${cleanName}`;

    const ghRes = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/forecast-request.yml/dispatches`, {
      method: 'POST',
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        'Content-Type': 'application/json',
        'User-Agent': 'weatherman-dispatch-function',
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: {
          slug,
          use_m5: String(useM5),
          m5_series_count: String(Number.isFinite(nSeries) ? nSeries : 3),
          payload: JSON.stringify(payloadObj),
          backtest_windows: String(body.backtest_windows ?? 3),
        },
      }),
    });

    if (!ghRes.ok) {
      const text = await ghRes.text();
      return new Response(JSON.stringify({ error: `GitHub API ${ghRes.status}: ${text}` }), {
        status: 502,
        headers: JSON_HEADERS,
      });
    }

    return new Response(JSON.stringify({ ok: true, message: 'Workflow dispatched', slug }), {
      status: 200,
      headers: JSON_HEADERS,
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err?.message || 'Unknown error' }), {
      status: 500,
      headers: JSON_HEADERS,
    });
  }
};
