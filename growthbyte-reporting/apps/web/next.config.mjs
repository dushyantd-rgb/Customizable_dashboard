import path from "node:path";
import { fileURLToPath } from "node:url";

const webDirectory = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: path.join(webDirectory, "../.."),
  transpilePackages: ["@growthbyte/config", "@growthbyte/shared-types", "@growthbyte/ui"],
};

export default nextConfig;
