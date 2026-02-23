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
  const pst = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Los_Angeles' }));
  const yyyy = pst.getFullYear();
  const mm = String(pst.getMonth() + 1).padStart(2, '0');
  const dd = String(pst.getDate()).padStart(2, '0');
  const hh = String(pst.getHours()).padStart(2, '0');
  const mi = String(pst.getMinutes()).padStart(2, '0');
  const ss = String(pst.getSeconds()).padStart(2, '0');
  return `${yyyy}${mm}${dd}-${hh}${mi}${ss}-pst`;
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
    const repo = String(body.repo || '').trim() || 'bryanwhiting/forecastingapi';
    const allowedRepo = env.ALLOWED_REPO || 'bryanwhiting/forecastingapi';
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
    if (useM5) {
      payloadObj.series_names = ['demo_mode_m5'];
      payloadObj.series_data = [];
    } else {
      const names = Array.isArray(payloadObj.series_names) ? payloadObj.series_names : [];
      const values = Array.isArray(payloadObj.series_data) ? payloadObj.series_data : [];
      if (names.includes('demo_mode_m5')) {
        return new Response(JSON.stringify({ error: 'series_names cannot include "demo_mode_m5" outside demo mode' }), {
          status: 400,
          headers: JSON_HEADERS,
        });
      }
      if (names.length !== values.length) {
        return new Response(JSON.stringify({ error: 'len(series_names) must equal len(series_data)' }), {
          status: 400,
          headers: JSON_HEADERS,
        });
      }
    }

    const cleanName = sanitizeSlug(runNameRaw) || 'forecast';
    const slug = `${timestampPrefix()}-${cleanName}`;

    const ghRes = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/forecast-request.yml/dispatches`, {
      method: 'POST',
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        'Content-Type': 'application/json',
        'User-Agent': 'forecastingapi-dispatch-function',
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: {
          slug,
          use_m5: String(useM5),
          m5_series_count: "3",
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

    const actionsUrl = `https://github.com/${repo}/actions/workflows/forecast-request.yml`;
    const statusUrl = `/api/run-status?slug=${encodeURIComponent(slug)}`;
    return new Response(JSON.stringify({ ok: true, message: 'Workflow dispatched', slug, actions_url: actionsUrl, status_url: statusUrl }), {
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
