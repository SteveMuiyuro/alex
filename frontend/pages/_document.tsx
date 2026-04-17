import { Html, Head, Main, NextScript } from "next/document";
import { withSiteUrl } from "@/lib/site-url";

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <link rel="icon" href={withSiteUrl("/favicon.ico")} />
        <link rel="icon" type="image/svg+xml" href={withSiteUrl("/favicon.svg")} />
        <link rel="apple-touch-icon" href={withSiteUrl("/favicon.ico")} />
        <link rel="manifest" href={withSiteUrl("/manifest.json")} />
        <meta name="description" content="Alex AI Financial Advisor - Your intelligent portfolio management assistant" />
        <meta name="theme-color" content="#209DD7" />
      </Head>
      <body className="antialiased">
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
