// audit.mjs 
import { promises as fs } from "fs"; 
import path from "path"; 

const ROOT = process.cwd(); 
const IGNORE = new Set(["node_modules", ".git", ".next", "dist", "build", ".output", ".vercel", ".nuxt"]); 
const FRAMEWORK_HINTS = [ 
  { name: "Next.js", files: ["next.config.js", "next.config.mjs", "app", "pages"] }, 
  { name: "Nuxt", files: ["nuxt.config.ts", "nuxt.config.js"] }, 
  { name: "Vite", files: ["vite.config.ts", "vite.config.js"] }, 
  { name: "CRA (React)", files: ["src/index.tsx", "src/index.jsx", "public/index.html"] }, 
  { name: "SvelteKit", files: ["svelte.config.js", "svelte.config.ts", "src/routes"] }, 
  { name: "Astro", files: ["astro.config.mjs", "src/pages"] }, 
  { name: "Django", files: ["manage.py", "templates"] }, 
]; 

const exts = { 
  img: new Set([".jpg",".jpeg",".png",".webp",".avif",".gif",".svg"]), 
  html: new Set([".html"]), 
  css: new Set([".css", ".scss", ".sass"]), 
  js: new Set([".js",".mjs",".cjs",".ts",".tsx",".jsx"]), 
}; 

const summary = { 
  root: ROOT, 
  detectedFrameworks: [], 
  packageJson: null, 
  scripts: {}, 
  deps: { direct: [], dev: [] }, 
  filesCount: { total: 0, img: 0, html: 0, css: 0, js: 0, other: 0 }, 
  imagesByType: { jpg:0, png:0, webp:0, avif:0, svg:0, other:0 }, 
  routesGuess: [], 
  htmlSeoCheck: [], 
  hasJsonLd: false, 
  envFiles: [], 
  todoNotes: [], 
}; 

async function walk(dir) { 
  const entries = await fs.readdir(dir, { withFileTypes: true }); 
  for (const e of entries) { 
    if (IGNORE.has(e.name)) continue; 
    const fp = path.join(dir, e.name); 
    if (e.isDirectory()) { 
      await walk(fp); 
      continue; 
    } 
    summary.filesCount.total++; 
    const ext = path.extname(e.name).toLowerCase(); 
    if (exts.img.has(ext)) { 
      summary.filesCount.img++; 
      if (ext === ".jpg" || ext === ".jpeg") summary.imagesByType.jpg++; 
      else if (ext === ".png") summary.imagesByType.png++; 
      else if (ext === ".webp") summary.imagesByType.webp++; 
      else if (ext === ".avif") summary.imagesByType.avif++; 
      else if (ext === ".svg") summary.imagesByType.svg++; 
      else summary.imagesByType.other++; 
    } else if (exts.html.has(ext)) summary.filesCount.html++; 
    else if (exts.css.has(ext)) summary.filesCount.css++; 
    else if (exts.js.has(ext)) summary.filesCount.js++; 
    else summary.filesCount.other++; 

    // routes guess 
    if (/(pages|app|src\/pages|src\/routes|routes|templates)/.test(fp) && /(\.tsx?|\.jsx?|\.html)$/.test(fp)) { 
      summary.routesGuess.push(fp.replace(ROOT + path.sep, "")); 
    } 

    // env 
    if (/\.env(\..+)?$/.test(e.name)) summary.envFiles.push(fp.replace(ROOT + path.sep, "")); 

    // TODO / FIXME notes 
    if (/\.(tsx?|jsx?|css|scss|sass|html|md)$/.test(ext)) { 
      const content = await fs.readFile(fp, "utf8").catch(()=>null); 
      if (content && /(TODO|FIXME)/.test(content)) { 
        const lines = content.split("\n").slice(0,3000); 
        lines.forEach((line, i)=>{ 
          if (/(TODO|FIXME)/.test(line)) { 
            summary.todoNotes.push({ file: fp.replace(ROOT + path.sep, ""), line: i+1, text: line.trim().slice(0,180) }); 
          } 
        }); 
      } 
      // minimal HTML SEO check 
      if (ext === ".html") { 
        const hasTitle = /<title>.*?<\/title>/i.test(content); 
        const hasDesc = /<meta\s+name=["']description["']\s+content=["'][^"']+["']\s*\/?>/i.test(content); 
        const hasViewport = /<meta\s+name=["']viewport["']/i.test(content); 
        const hasCanonical = /<link\s+rel=["']canonical["']\s+href=["'][^"']+["']\s*\/?>/i.test(content); 
        const hasJsonLd = /<script[^>]+type=["']application\/ld\+json["'][^>]*>[\s\S]*?<\/script>/i.test(content); 
        if (hasJsonLd) summary.hasJsonLd = true; 
        summary.htmlSeoCheck.push({ 
          file: fp.replace(ROOT + path.sep, ""), 
          title: hasTitle, description: hasDesc, viewport: hasViewport, canonical: hasCanonical, jsonld: hasJsonLd 
        }); 
      } 
    } 
  } 
} 

async function detectFramework() { 
  const names = new Set(); 
  // package.json 
  try { 
    const pkgRaw = await fs.readFile(path.join(ROOT, "package.json"), "utf8"); 
    const pkg = JSON.parse(pkgRaw); 
    summary.packageJson = { name: pkg.name, version: pkg.version }; 
    summary.scripts = pkg.scripts || {}; 
    summary.deps.direct = Object.keys(pkg.dependencies || {}); 
    summary.deps.dev = Object.keys(pkg.devDependencies || {}); 
    const depJoin = [...summary.deps.direct, ...summary.deps.dev].join(","); 
    if (/next/.test(depJoin)) names.add("Next.js"); 
    if (/nuxt/.test(depJoin)) names.add("Nuxt"); 
    if (/vite/.test(depJoin)) names.add("Vite"); 
    if (/react-scripts/.test(depJoin)) names.add("CRA (React)"); 
    if (/svelte|@sveltejs\/kit/.test(depJoin)) names.add("Svelte/SvelteKit"); 
    if (/astro/.test(depJoin)) names.add("Astro"); 
  } catch {} 
  // hint files 
  const all = await fs.readdir(ROOT); 
  for (const fw of FRAMEWORK_HINTS) { 
    for (const f of fw.files) { 
      if (all.includes(f) || (await exists(path.join(ROOT, f)))) names.add(fw.name); 
    } 
  } 
  summary.detectedFrameworks = [...names]; 
} 

async function exists(p) { try { await fs.access(p); return true; } catch { return false; } } 

(async ()=>{ 
  await detectFramework(); 
  await walk(ROOT); 
  // kısa öneriler 
  const suggestions = []; 
  if (summary.imagesByType.webp === 0 && summary.imagesByType.avif === 0) { 
    suggestions.push("Görsellerde WebP/AVIF kullanımı yok: temel ürün görsellerini WebP/AVIF'e dönüştürün."); 
  } 
  if (!summary.hasJsonLd) suggestions.push("HTML'de Product/Organization JSON‑LD bulunamadı: arama görünürlüğü için ekleyin."); 
  if (!Object.keys(summary.scripts).length) suggestions.push("package.json scripts boş görünüyor: build/dev/test komutlarını tanımlayın."); 
  console.log(JSON.stringify({summary, suggestions}, null, 2)); 
})();