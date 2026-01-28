export default {
  /**
   * Cron trigger handler - dispatches GitHub Actions workflows
   */
  async scheduled(event, env, ctx) {
    const workflows = [
      { name: 'marketing-cleanup.yml', id: 225917809 },
      { name: 'job-app-cleanup.yml', id: 225917808 }
    ];

    const results = await Promise.all(
      workflows.map(async (workflow) => {
        try {
          const response = await fetch(
            `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${workflow.id}/dispatches`,
            {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'CF-Worker-Cron'
              },
              body: JSON.stringify({ ref: 'main' })
            }
          );

          return {
            workflow: workflow.name,
            status: response.status,
            success: response.status === 204
          };
        } catch (error) {
          return {
            workflow: workflow.name,
            status: 'error',
            success: false,
            error: error.message
          };
        }
      })
    );

    console.log('Workflow dispatch results:', JSON.stringify(results, null, 2));

    // Log individual results for easier filtering in dashboard
    results.forEach(r => {
      if (r.success) {
        console.log(`✓ ${r.workflow} dispatched successfully`);
      } else {
        console.error(`✗ ${r.workflow} failed: ${r.status} ${r.error || ''}`);
      }
    });

    return results;
  },

  /**
   * HTTP handler - for manual testing
   */
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Health check endpoint
    if (url.pathname === '/health') {
      return new Response(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Manual trigger endpoint (POST only)
    if (request.method === 'POST') {
      const results = await this.scheduled({}, env, ctx);
      return new Response(JSON.stringify(results, null, 2), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Default response
    return new Response(
      'Gmail Cleanup Cron Trigger Worker\n\n' +
      'Endpoints:\n' +
      '  GET  /health - Health check\n' +
      '  POST /       - Manually trigger workflows\n\n' +
      'Cron: Every 6 hours (0 */6 * * *)',
      { status: 200, headers: { 'Content-Type': 'text/plain' } }
    );
  }
};
