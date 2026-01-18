const path = require("path");
const { CleanWebpackPlugin } = require("clean-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");
const { ProvidePlugin, SourceMapDevToolPlugin } = require("webpack");
const TerserPlugin = require("terser-webpack-plugin");
const CopyPlugin = require("copy-webpack-plugin");
const BundleTracker = require("webpack-bundle-tracker");

const opts = require("./package.json").options;

module.exports = (_, argv) => {
	const dev = argv.mode === "development";

	const config = {
		context: path.resolve(__dirname, opts.src),

		devtool: false,
		target: ["web", "es5"],

		entry: opts.entry,

		stats: {
			loggingDebug: ["sass-loader"],
		},

		output: {
			filename: dev ? "js/[name].js" : "js/[contenthash].[name].js",
			path: path.resolve(__dirname, opts.output),
			publicPath: opts.publicPath,
			assetModuleFilename: (arg) => {
				let sep = path.normalize(`/${opts.src}/`);
				let pth = arg.module.context.split(sep).pop();
				return path.join(pth, "[name][ext]").replaceAll("\\", "/");
			},
		},

		module: {
			rules: [
				// Scripts
				{
					test: /\.m?js$/,
					exclude: /(node_modules|bower_components)/,
					use: [
						{
							loader: "babel-loader",
							options: {
								presets: ["@babel/preset-env"],
								plugins: [
									[
										"@babel/plugin-transform-runtime",
										{
											corejs: 3,
											regenerator: true,
										},
									],
								],
							},
						},
					],
				},

				// Styles
				{
					test: /\.s[ac]ss$/i,
					use: [
						{
							loader: MiniCssExtractPlugin.loader,
						},
						"css-loader",
						{
							loader: "postcss-loader",
							options: {
								postcssOptions: {
									plugins: [
										[
											"postcss-preset-env",
											{
												autoprefixer: {
													flexbox: "no-2009",
													grid: true,
												},
											},
										],
										require("postcss-sort-media-queries")(),
										require("postcss-merge-rules")(),
									],
								},
							},
						},
						{
							loader: "sass-loader",
							options: {
								sourceMap: true,
							},
						},
					],
				},

				// SVG/HTML
				{
					test: /\.(svg|html)$/,
					loader: "html-loader",
					include: path.resolve(__dirname, opts.icons),
				},
			],
		},

		resolve: {
			alias: {
				"@src": path.resolve(__dirname, opts.src),
				"@icons": path.resolve(__dirname, opts.icons),
			},
		},

		plugins: [
			new CleanWebpackPlugin(),
			new CopyPlugin({
				patterns: opts.copy.map((obj) => {
					return {
						from: path.resolve(__dirname, obj.from),
						to: path.resolve(__dirname, obj.to),
						noErrorOnMissing: true,
					};
				}),
			}),
			new MiniCssExtractPlugin({
				filename: dev ? "css/[name].css" : "css/[contenthash].[name].css",
			}),
			new ProvidePlugin({
				$: "jquery",
				jQuery: "jquery",
				"window.jQuery": "jquery",
			}),
			new BundleTracker({ filename: "webpack-stats.json" }),
		],

		optimization: {
			splitChunks: {
				chunks: "all",
			},
			minimizer: [
				new CssMinimizerPlugin({
					minimizerOptions: {
						preset: [
							"default",
							{
								discardComments: { removeAll: true },
							},
						],
					},
				}),
				new TerserPlugin(),
			],
		},

		devServer: {
			port: opts.port,
			host: opts.host,
			hot: true,
			compress: false,
			static: false,
			devMiddleware: {
				index: false, // specify to enable root proxying
			},
			proxy: [
				{
					context: () => true,
					target: opts.proxy,
				},
			],
			allowedHosts: "*",
			headers: { "Access-Control-Allow-Origin": "*" },
			watchFiles: {
				paths: opts.watch.map((app) => `./${app}/templates/**/*.{html,svg}`),
				options: {
					usePolling: false,
					awaitWriteFinish: {
						stabilityTreshold: 1000,
						pollInterval: 100,
					},
				},
			},
		},
	};

	if (argv.mode === "development") {
		config.plugins.push(new SourceMapDevToolPlugin({}));
	}

	return config;
};
