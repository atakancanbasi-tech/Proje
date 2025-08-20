// html-lint.mjs 
import { promises as fs } from "fs"; 
import path from "path"; 
const ROOT = process.cwd(); 
const IGNORE = new Set(["node_modules",".git",".next","dist","build",".output",".vercel",".nuxt"]); 

const results = []; 
async function walk(dir){ 
  const entries = await fs.readdir(dir, { withFileTypes:true }); 
  for (const e of entries){ 
    if (IGNORE.has(e.name)) continue; 
    const fp = path.join(dir, e.name); 
    if (e.isDirectory()) { await walk(fp); continue; } 
    if (path.extname(e.name).toLowerCase() === ".html") { 
      const html = await fs.readFile(fp, "utf8").catch(()=>null); 
      if (!html) continue; 
      const imgs = [...html.matchAll(/<img\b[^>]*>/gi)]; 
      imgs.forEach((m,i)=>{ 
        const tag = m[0]; 
        const hasAlt = /\balt=/.test(tag); 
        const hasW = /\bwidth=/.test(tag); 
        const hasH = /\bheight=/.test(tag); 
        const hasLazy = /\bloading=["']lazy["']/.test(tag); 
        const hasDec = /\bdecoding=["']async["']/.test(tag); 
        results.push({ 
          file: fp.replace(ROOT + path.sep, ""), index: i+1, 
          ok: hasAlt && hasW && hasH && hasLazy && hasDec, 
          alt: hasAlt, width: hasW, height: hasH, lazy: hasLazy, decodingAsync: hasDec, 
          tag: tag.slice(0,180) 
        }); 
      }); 
    } 
  } 
} 
(async ()=>{ 
  await walk(ROOT); 
  const missing = results.filter(r=>!r.ok); 
  console.log(JSON.stringify({totalImgs: results.length, issues: missing.length, details: missing.slice(0,200)}, null, 2)); 
})();