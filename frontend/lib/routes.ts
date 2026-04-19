import { withSiteUrl } from "./site-url";

export const HOME_ROUTE = "/index.html";
export const DASHBOARD_ROUTE = "/dashboard.html";
export const ACCOUNTS_ROUTE = "/accounts.html";
export const ADVISOR_TEAM_ROUTE = "/advisor-team.html";
export const ANALYSIS_ROUTE = "/analysis.html";

export const CLERK_HOME_URL = withSiteUrl(HOME_ROUTE);
export const CLERK_DASHBOARD_URL = withSiteUrl(DASHBOARD_ROUTE);
export const CLERK_ACCOUNTS_URL = withSiteUrl(ACCOUNTS_ROUTE);
export const CLERK_ADVISOR_TEAM_URL = withSiteUrl(ADVISOR_TEAM_ROUTE);
export const CLERK_ANALYSIS_URL = withSiteUrl(ANALYSIS_ROUTE);

export function advisorTeamRoute(autoStart = false): string {
  if (!autoStart) {
    return ADVISOR_TEAM_ROUTE;
  }

  return `${ADVISOR_TEAM_ROUTE}?autostart=1`;
}

export function analysisRoute(jobId?: string): string {
  if (!jobId) {
    return ANALYSIS_ROUTE;
  }

  return `${ANALYSIS_ROUTE}?job_id=${encodeURIComponent(jobId)}`;
}
