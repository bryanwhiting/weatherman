interface Env {
  GITHUB_TOKEN: string;
  ALLOWED_REPO?: string;
}

const JSON_HEADERS = {
  'content-type': 'application/json',
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, OPTIONS',
  'access-control-allow-headers': 'content-type',
};

export const onRequestOptions = async () => new Response(null, { status: 204, headers: JSON_HEADERS });

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  try {
    const url = new URL(request.url);
    const slug = (url.searchParams.get('slug') || '').trim();
    if (!slug) {
      return new Response(JSON.stringify({ error: 'slug is required' }), { status: 400, headers: JSON_HEADERS });
    }

    const repo = env.ALLOWED_REPO || 'bryanwhiting/forecastingapi';
    const gh = await fetch(`https://api.github.com/repos/${repo}/actions/runs?per_page=30`, {
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        'User-Agent': 'weatherman-run-status',
      },
    });

    if (!gh.ok) {
      const txt = await gh.text();
      return new Response(JSON.stringify({ error: `GitHub API ${gh.status}: ${txt}` }), { status: 502, headers: JSON_HEADERS });
    }

    const data = await gh.json<any>();
    const runs = Array.isArray(data?.workflow_runs) ? data.workflow_runs : [];

    const match = runs.find((r) => {
      const name = String(r?.name || '');
      const display = String(r?.display_title || '');
      const runName = String(r?.run_number || '');
      const event = String(r?.event || '');
      return event === 'workflow_dispatch' && (display.includes(slug) || name.includes('Forecast Request'));
    });

    if (!match) {
      return new Response(JSON.stringify({ found: false, slug, status: 'not_found' }), { status: 200, headers: JSON_HEADERS });
    }

    return new Response(
      JSON.stringify({
        found: true,
        slug,
        id: match.id,
        status: match.status,
        conclusion: match.conclusion,
        html_url: match.html_url,
        created_at: match.created_at,
        updated_at: match.updated_at,
      }),
      { status: 200, headers: JSON_HEADERS }
    );
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err?.message || 'Unknown error' }), { status: 500, headers: JSON_HEADERS });
  }
};
