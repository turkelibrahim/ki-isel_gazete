let esbuild = null;
try {
  esbuild = require("esbuild");
} catch (error) {
  esbuild = null;
}

const fs = require("fs");
const path = require("path");

function localFilePlugin() {
  return {
    name: "local-file-resolver",
    setup(build) {
      build.onResolve({ filter: /^[^./]|^@/ }, (args) => {
        const parts = args.path.split("/");
        const packageName = args.path.startsWith("@") ? parts.slice(0, 2).join("/") : parts[0];
        const subPath = args.path.startsWith("@") ? parts.slice(2).join("/") : parts.slice(1).join("/");
        const packageDir = path.join(__dirname, "node_modules", packageName);
        const packageJsonPath = path.join(packageDir, "package.json");
        if (!fs.existsSync(packageJsonPath)) return null;
        const manifest = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
        const browserField = typeof manifest.browser === "string" ? manifest.browser : "";
        const entry = subPath || browserField || manifest.module || manifest.main || "index.js";
        const candidate = path.join(packageDir, entry);
        const paths = path.extname(candidate)
          ? [candidate]
          : [candidate, `${candidate}.js`, `${candidate}.mjs`, `${candidate}.cjs`, path.join(candidate, "index.js")];
        const resolved = paths.find((item) => fs.existsSync(item) && fs.statSync(item).isFile());
        return resolved ? { path: resolved } : null;
      });

      build.onResolve({ filter: /^\./ }, (args) => {
        const baseDir = args.resolveDir || __dirname;
        const candidate = path.resolve(baseDir, args.path);
        const paths = path.extname(candidate)
          ? [candidate]
          : [candidate, `${candidate}.js`, `${candidate}.css`];
        const resolved = paths.find((item) => fs.existsSync(item) && fs.statSync(item).isFile());
        if (!resolved) return null;
        return { path: resolved };
      });

      build.onLoad({ filter: /\.(mjs|cjs|js|css)$/ }, (args) => ({
        contents: fs.readFileSync(args.path, "utf8"),
        loader: path.extname(args.path) === ".css" ? "css" : "js"
      }));
    }
  };
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function stripCssComments(input) {
  return input.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\s+/g, " ").trim();
}

function copyDirRecursive(src, dest) {
  if (!fs.existsSync(src)) return;
  ensureDir(dest);
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDirRecursive(from, to);
    else fs.copyFileSync(from, to);
  }
}

function writeFallbackBuild(distDir, cssFiles) {
  console.warn("esbuild bulunamadı/çalıştırılamadı; dependency kurulmadan çalışabilmesi için güvenli fallback build üretildi.");
  fs.copyFileSync(path.join(__dirname, "js", "app.js"), path.join(distDir, "app.min.js"));
  ["components", "services", "utils", "data"].forEach((dir) => copyDirRecursive(path.join(__dirname, "js", dir), path.join(distDir, dir)));
  fs.writeFileSync(
    path.join(distDir, "app.min.js.map"),
    JSON.stringify({ version: 3, sources: ["../js/app.js"], names: [], mappings: "" }, null, 2)
  );

  const existingCssFiles = cssFiles.filter((filePath) => fs.existsSync(path.join(__dirname, filePath)));
  const cssContents = existingCssFiles.map((filePath) => fs.readFileSync(path.join(__dirname, filePath), "utf8")).join("\n");
  fs.writeFileSync(path.join(distDir, "style.min.css"), stripCssComments(cssContents));

  const mockPath = path.join(__dirname, "js", "mock-data.js");
  if (fs.existsSync(mockPath)) {
    fs.copyFileSync(mockPath, path.join(distDir, "mock-data.min.js"));
  }
}

async function build() {
  const distDir = path.join(__dirname, "dist");
  ensureDir(distDir);

  const cssFiles = ["css/style.css", "css/dashboard.css", "css/egazete.css", "css/chatbot.css", "css/feedback.css"];

  if (!esbuild) {
    writeFallbackBuild(distDir, cssFiles);
    console.log("\nFallback build tamamlandı. Tam minify için npm install sonrası npm run build tekrar çalıştırılabilir.");
    return;
  }

  try {
    const appEntry = path.join(__dirname, "js", "app.js");
    await esbuild.build({
      stdin: {
        contents: fs.readFileSync(appEntry, "utf8"),
        resolveDir: path.dirname(appEntry),
        sourcefile: appEntry,
        loader: "js"
      },
      bundle: true,
      minify: true,
      sourcemap: true,
      format: "esm",
      outfile: path.join(distDir, "app.min.js"),
      target: ["es2020"],
      logLevel: "info",
      plugins: [localFilePlugin()]
    });

    const existingCssFiles = cssFiles.filter((filePath) => fs.existsSync(path.join(__dirname, filePath)));
    const cssContents = existingCssFiles.map((filePath) => fs.readFileSync(path.join(__dirname, filePath), "utf8")).join("\n");
    const tmpCss = path.join(__dirname, "css", "_combined.css");
    fs.writeFileSync(tmpCss, cssContents);

    await esbuild.build({
      stdin: {
        contents: fs.readFileSync(tmpCss, "utf8"),
        resolveDir: path.dirname(tmpCss),
        sourcefile: tmpCss,
        loader: "css"
      },
      bundle: true,
      minify: true,
      outfile: path.join(distDir, "style.min.css"),
      logLevel: "info",
      plugins: [localFilePlugin()]
    });

    fs.unlinkSync(tmpCss);

    const mockPath = path.join(__dirname, "js", "mock-data.js");
    if (fs.existsSync(mockPath)) {
      const mockData = fs.readFileSync(mockPath, "utf8");
      const mockResult = await esbuild.transform(mockData, { minify: true });
      fs.writeFileSync(path.join(distDir, "mock-data.min.js"), mockResult.code);
    }

    const origJs = fs.statSync("js/app.js").size;
    const minJs = fs.statSync(path.join(distDir, "app.min.js")).size;
    const origCss = existingCssFiles.reduce((sum, filePath) => sum + fs.statSync(path.join(__dirname, filePath)).size, 0);
    const minCss = fs.statSync(path.join(distDir, "style.min.css")).size;

    console.log(`\nJS:  ${(origJs / 1024).toFixed(0)}KB -> ${(minJs / 1024).toFixed(0)}KB (${(100 - minJs / origJs * 100).toFixed(0)}% reduction)`);
    console.log(`CSS: ${(origCss / 1024).toFixed(0)}KB -> ${(minCss / 1024).toFixed(0)}KB (${(100 - minCss / origCss * 100).toFixed(0)}% reduction)`);
  } catch (error) {
    console.warn(`esbuild çalıştırılamadı (${String(error.message || error).split("\n")[0]}); güvenli fallback build üretildi.`);
    writeFallbackBuild(distDir, cssFiles);
    console.log("\nFallback build tamamlandı.");
  }
}

build().catch((error) => {
  console.error(error);
  process.exit(1);
});
