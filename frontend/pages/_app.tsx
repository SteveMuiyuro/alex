import "@/styles/globals.css";
import type { AppProps } from "next/app";
import { ClerkProvider } from "@clerk/nextjs";
import { ToastContainer } from "@/components/Toast";
import ErrorBoundary from "@/components/ErrorBoundary";
import { CLERK_DASHBOARD_URL } from "@/lib/routes";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ErrorBoundary>
      <ClerkProvider
        {...pageProps}
        signInFallbackRedirectUrl={CLERK_DASHBOARD_URL}
        signUpFallbackRedirectUrl={CLERK_DASHBOARD_URL}
        signInForceRedirectUrl={CLERK_DASHBOARD_URL}
        signUpForceRedirectUrl={CLERK_DASHBOARD_URL}
      >
        <Component {...pageProps} />
        <ToastContainer />
      </ClerkProvider>
    </ErrorBoundary>
  );
}
