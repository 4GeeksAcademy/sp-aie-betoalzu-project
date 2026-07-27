import type { NextConfig } from "next";

const nextConfig: NextConfig = {
	async redirects() {
		return [
			{
				source: "/website",
				destination: "/",
				permanent: false,
			},
			{
				source: "/website/:path*",
				destination: "/:path*",
				permanent: false,
			},
		];
	},
};

export default nextConfig;
