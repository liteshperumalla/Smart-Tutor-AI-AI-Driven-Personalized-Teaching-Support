const START_TIME_SECONDS = Date.now() / 1000;

function formatMetrics(): string {
  const nowSeconds = Date.now() / 1000;
  const uptimeSeconds = Math.max(0, nowSeconds - START_TIME_SECONDS);

  return [
    "# HELP frontend_up Frontend availability",
    "# TYPE frontend_up gauge",
    "frontend_up 1",
    "# HELP frontend_start_time_seconds Frontend start time in seconds since epoch",
    "# TYPE frontend_start_time_seconds gauge",
    `frontend_start_time_seconds ${START_TIME_SECONDS.toFixed(0)}`,
    "# HELP frontend_uptime_seconds Frontend uptime in seconds",
    "# TYPE frontend_uptime_seconds counter",
    `frontend_uptime_seconds ${uptimeSeconds.toFixed(0)}`,
    "",
  ].join("\n");
}

export async function GET() {
  return new Response(formatMetrics(), {
    status: 200,
    headers: {
      "Content-Type": "text/plain; version=0.0.4; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
