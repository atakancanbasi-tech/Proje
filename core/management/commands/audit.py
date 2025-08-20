import json, os, re
from pathlib import Path
from datetime import datetime
from django import get_version as djv
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import get_resolver, URLPattern, URLResolver

BASE=Path(settings.BASE_DIR)
IMG=re.compile(r"<img\s+[^>]*>",re.I)
W=re.compile(r"\bwidth\s*=",re.I)
H=re.compile(r"\bheight\s*=",re.I)
ALT=re.compile(r"\balt\s*=",re.I)
SRCH=re.compile(r'<input[^>]*type="search"[^>]*>',re.I)
ARIA=re.compile(r'aria-label\s*=',re.I)
CSS_EMPTY=re.compile(r":\s*;")
CSS_PROP_EMPTY=re.compile(r"(width|height|background-color|color|padding|margin|font-size)\s*:\s*;")
TAG_IMG_DEFAULT=re.compile(r"\{%\s*img_default_attrs\s+(\d+)\s+(\d+)\s*%\}", re.I)

def _walk(root,exts):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts: yield p

def _scan_templates():
    dirs=[]
    for t in settings.TEMPLATES: dirs+=list(map(Path,t.get("DIRS",[])))
    dirs+=[(BASE/"shop/templates"),(BASE/"accounts/templates")]
    seen=set(); out={"img_missing_dimensions":[], "img_missing_alt":[], "search_missing_aria":[]}
    for d in dirs:
        if not d.exists(): continue
        for f in _walk(d,{".html",".htm"}):
            if f in seen: continue
            seen.add(f)
            try: txt=f.read_text(encoding="utf-8",errors="ignore")
            except: continue
            tags=IMG.findall(txt)
            # width/height mevcut mu? img_default_attrs kullanımı da kabul edilir
            def _has_dims(t:str)->bool:
                return bool(W.search(t) and H.search(t)) or bool(TAG_IMG_DEFAULT.search(t))
            if tags and any((not _has_dims(t)) for t in tags): out["img_missing_dimensions"].append(str(f))
            if tags and any((not ALT.search(t)) for t in tags): out["img_missing_alt"].append(str(f))
            s=SRCH.findall(txt)
            if s and any((not ARIA.search(x)) for x in s): out["search_missing_aria"].append(str(f))
    return out

def _scan_css():
    root=BASE/"static/css"
    out={"empty_declarations":[], "prop_empty":[]}
    if root.exists():
        for f in _walk(root,{".css"}):
            try: txt=f.read_text(encoding="utf-8",errors="ignore")
            except: continue
            if CSS_EMPTY.search(txt): out["empty_declarations"].append(str(f))
            if CSS_PROP_EMPTY.search(txt): out["prop_empty"].append(str(f))
    return out

def _urls():
    r = get_resolver()
    names = {}
    total = 0

    def walk(pats, ns_parts):
        nonlocal total
        for p in pats:
            if isinstance(p, URLPattern):
                total += 1
                if p.name:
                    full = ":".join([*ns_parts, p.name]) if ns_parts else p.name
                    names[full] = names.get(full, 0) + 1
            elif isinstance(p, URLResolver):
                next_ns = [*ns_parts, p.namespace] if p.namespace else ns_parts
                walk(p.url_patterns, next_ns)

    walk(r.url_patterns, [])
    dups = [k for k, v in names.items() if v > 1]
    return {"total": total, "duplicates": dups}

def _security():
    have={
        "DEBUG": settings.DEBUG,
        "ALLOWED_HOSTS_len": len(getattr(settings,"ALLOWED_HOSTS",[])),
        "SECURE_SSL_REDIRECT": getattr(settings,"SECURE_SSL_REDIRECT",False),
        "SESSION_COOKIE_SECURE": getattr(settings,"SESSION_COOKIE_SECURE",False),
        "CSRF_COOKIE_SECURE": getattr(settings,"CSRF_COOKIE_SECURE",False),
        "SECURE_HSTS_SECONDS": getattr(settings,"SECURE_HSTS_SECONDS",0),
        "WHITENOISE": any("whitenoise" in m.lower() for m in settings.MIDDLEWARE),
        "STATICFILES_STORAGE": getattr(settings,"STATICFILES_STORAGE",""),
        "SENTRY_DSN_set": bool(os.getenv("SENTRY_DSN") or getattr(settings,"SENTRY_DSN",None)),
    }
    findings=[]
    if not settings.DEBUG:
        if not have["SECURE_SSL_REDIRECT"]: findings.append("SECURE_SSL_REDIRECT=False")
        if not have["SESSION_COOKIE_SECURE"]: findings.append("SESSION_COOKIE_SECURE=False")
        if not have["CSRF_COOKIE_SECURE"]: findings.append("CSRF_COOKIE_SECURE=False")
        if have["SECURE_HSTS_SECONDS"]<31536000: findings.append("SECURE_HSTS_SECONDS<31536000")
        if have["ALLOWED_HOSTS_len"]==0: findings.append("ALLOWED_HOSTS boş")
        if not have["WHITENOISE"]: findings.append("WhiteNoise middleware yok")
        if "CompressedManifest" not in have["STATICFILES_STORAGE"]: findings.append("STATICFILES_STORAGE manifest değil")
        if not have["SENTRY_DSN_set"]: findings.append("Sentry DSN yok")
    return {"have":have,"findings":findings}

class Command(BaseCommand):
    help="Projeyi güvenlik/erişilebilirlik/CSS/URL açısından tarar."
    def add_arguments(self,parser):
        parser.add_argument("--write",help="JSON rapor yolu, örn: var/reports/audit.json")
        parser.add_argument("--pretty",action="store_true")
    def handle(self,*a,**o):
        rep={
            "time":datetime.utcnow().isoformat()+"Z",
            "django":djv(),
            "debug":settings.DEBUG,
            "sections":{
                "security":_security(),
                "urls":_urls(),
                "templates":_scan_templates(),
                "css":_scan_css(),
            }
        }
        tips=[]
        if not settings.DEBUG and rep["sections"]["security"]["findings"]:
            tips.append("Üretim güvenlik bayraklarını düzeltin (SSL/HSTS/secure cookies).")
        t=rep["sections"]["templates"]
        if t["img_missing_dimensions"]: tips.append("<img> width/height ekleyin (CLS).")
        if t["img_missing_alt"]: tips.append("<img alt> zorunlu (Erişilebilirlik).")
        if t["search_missing_aria"]: tips.append("Arama input'una aria-label ekleyin.")
        c=rep["sections"]["css"]
        if c["empty_declarations"] or c["prop_empty"]: tips.append("CSS boş deklarasyonları temizleyin.")
        rep["tips"]=tips
        if o.get("write"):
            p=BASE/o["write"]; p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"JSON yazıldı: {p}"))
        if o.get("pretty"): self.stdout.write(json.dumps(rep,ensure_ascii=False,indent=2))
        else:
            self.stdout.write("Audit: "+(", ".join(tips) if tips else "Önemli sorun yok."))