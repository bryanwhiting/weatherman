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

    const slug = String(body.slug || '').trim();
    if (!slug) {
      return new Response(JSON.stringify({ error: 'slug is required' }), {
        status: 400,
        headers: JSON_HEADERS,
      });
    }

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
          use_m5: String(Boolean(body.use_m5)),
          m5_series_count: String(body.m5_series_count ?? 3),
          payload: typeof body.payload === 'string' ? body.payload : JSON.stringify(body.payload || {}),
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

    return new Response(JSON.stringify({ ok: true, message: 'Workflow dispatched' }), {
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
