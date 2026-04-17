import type { NextConfig } from "next";
import { getSiteUrl } from "./lib/site-url";

const siteUrl = getSiteUrl();

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "export",
  assetPrefix: process.env.NODE_ENV === "production" && siteUrl ? siteUrl : undefined,
  images: {
    unoptimized: true,
  },
  trailingSlash: false,
};

export default nextConfig;
