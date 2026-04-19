interface JobProgress {
  percent: number;
  stage_key: string;
  message: string;
  active_agents: string[];
  payloads_completed?: {
    report: boolean;
    charts: boolean;
    retirement: boolean;
  };
}

interface AnalysisProgressCardProps {
  progress: JobProgress;
  isError?: boolean;
  errorMessage?: string;
}

const stageLabels: Record<string, string> = {
  queued: 'Queued',
  planner_started: 'Planner Started',
  tagging_instruments: 'Instrument Review',
  refreshing_market_data: 'Market Refresh',
  preparing_portfolio_context: 'Context Ready',
  running_reporter: 'Report Writer',
  running_charter: 'Chart Builder',
  running_retirement: 'Retirement Planner',
  finalizing: 'Finalizing',
  completed: 'Completed',
  failed: 'Failed',
};

export default function AnalysisProgressCard({
  progress,
  isError = false,
  errorMessage,
}: AnalysisProgressCardProps) {
  const payloads = progress.payloads_completed || {
    report: false,
    charts: false,
    retirement: false,
  };

  return (
    <div className={`mb-8 rounded-lg border p-6 ${
      isError ? 'border-red-200 bg-red-50' : 'border-ai-accent/20 bg-gradient-to-r from-ai-accent/10 to-primary/10'
    }`}>
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-dark">Analysis Progress</h3>
          <p className={`text-sm ${isError ? 'text-red-700' : 'text-gray-600'}`}>
            {errorMessage || progress.message}
          </p>
        </div>
        <div className={`rounded-full px-3 py-1 text-sm font-semibold ${
          isError ? 'bg-red-100 text-red-700' : 'bg-white/70 text-dark'
        }`}>
          {Math.max(0, Math.min(100, progress.percent))}%
        </div>
      </div>

      <div className="mb-4 h-3 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            isError ? 'bg-red-500' : 'bg-ai-accent'
          }`}
          style={{ width: `${Math.max(0, Math.min(100, progress.percent))}%` }}
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium text-gray-500">Current stage:</span>
        <span className="rounded-full bg-white px-3 py-1 text-dark shadow-sm">
          {stageLabels[progress.stage_key] || progress.stage_key}
        </span>
        {!isError && progress.active_agents.length > 0 && (
          <>
            <span className="font-medium text-gray-500">Active:</span>
            {progress.active_agents.map((agent) => (
              <span key={agent} className="rounded-full bg-dark px-3 py-1 text-white shadow-sm">
                {agent}
              </span>
            ))}
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2 text-sm text-gray-700 sm:grid-cols-3">
        <div className={`rounded-lg px-3 py-2 ${payloads.charts ? 'bg-green-50 text-green-700' : 'bg-white/70'}`}>
          Charts {payloads.charts ? 'ready' : 'pending'}
        </div>
        <div className={`rounded-lg px-3 py-2 ${payloads.retirement ? 'bg-green-50 text-green-700' : 'bg-white/70'}`}>
          Retirement outlook {payloads.retirement ? 'ready' : 'pending'}
        </div>
        <div className={`rounded-lg px-3 py-2 ${payloads.report ? 'bg-green-50 text-green-700' : 'bg-white/70'}`}>
          Portfolio report {payloads.report ? 'ready' : 'pending'}
        </div>
      </div>
    </div>
  );
}
