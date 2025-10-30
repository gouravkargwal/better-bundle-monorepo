// vite.config.ts
import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import { resolve } from "path";
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig(({ mode }) => {
  const isDev = mode === "development";
  const isAnalyze = mode === "analyze" || process.env.ANALYZE === "1";
  const outDir = resolve(
    __dirname,
    "..",
    "..",
    "extensions",
    "phoenix",
    "assets",
  );

  return {
    // Use any type to bypass plugin compatibility issues
    plugins: [
      preact() as any,
      // Bundle analyzer (enabled only in analyze mode)
      isAnalyze &&
        (visualizer({
          filename: resolve(__dirname, "bundle-analysis.html"),
          template: "treemap",
          open: false,
          gzipSize: true,
          brotliSize: true,
        }) as any),
      // CSS cleanup plugin
      {
        name: "cleanup-assets",
        enforce: "post" as const,
        generateBundle(_options: any, bundle: any) {
          for (const fileName of Object.keys(bundle)) {
            if (
              fileName.endsWith(".css") &&
              fileName !== "phoenix.css" &&
              /phoenix-.*\.css$/.test(fileName)
            ) {
              console.log(`🧹 Removing duplicate CSS: ${fileName}`);
              delete bundle[fileName];
            }
          }
        },
      },
    ].filter(Boolean) as any,

    resolve: {
      alias: {
        "@": resolve(__dirname, "./src"),
      },
    },

    build: {
      outDir,
      emptyOutDir: true,
      assetsDir: "",
      cssCodeSplit: false,
      reportCompressedSize: true,
      chunkSizeWarningLimit: 50,

      rollupOptions: {
        input: resolve(__dirname, "src", "index.tsx"),
        output: {
          entryFileNames: "phoenix.js",
          assetFileNames: "phoenix.[ext]",
          compact: true,
          inlineDynamicImports: true,
        },
        treeshake: {
          preset: "smallest",
          moduleSideEffects: false,
          propertyReadSideEffects: false,
          tryCatchDeoptimization: false,
          unknownGlobalSideEffects: false,
        },
      },

      target: "esnext",
      minify: "esbuild",
      sourcemap: false,
      cssMinify: "esbuild",
    },

    esbuild: {
      target: "esnext",
      drop: isDev ? [] : ["console", "debugger"],
      legalComments: "none",
      treeShaking: true,
      minifyIdentifiers: true,
      minifySyntax: true,
      minifyWhitespace: true,
      define: {
        __DEV__: "false",
      },
    },

    optimizeDeps: {
      include: ["preact", "preact/hooks"],
      esbuildOptions: {
        target: "esnext",
      },
    },

    server: {
      port: 5173,
      host: "localhost",
    },
  };
});
