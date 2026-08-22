"""
SCRAPER DE LEADS - Telefones / WhatsApp / Google Maps
=====================================================
- Extrai telefone/WhatsApp de Instagram, Facebook e Link-in-bio
- Gera leads do Google Maps (nicho + cidade + estado livres)
- Enriquece com e-mail, Instagram, Facebook, WhatsApp, etc.
- Playwright + suporte a extensão NopeCHA
- API REST com FastAPI
"""

import re
import logging
import time
import os
import asyncio
import random
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse, parse_qs, quote_plus, urljoin
from contextlib import contextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

try:
    from aiograpi import Client as InstagramClient
    HAS_AIOGRAPI = True
except ImportError:
    HAS_AIOGRAPI = False

from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("scraper-leads")

app = FastAPI(
    title="Scraper de Leads",
    description="Telefones, WhatsApp, Google Maps, e-mails e redes sociais",
    version="2.0.0",
)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

PHONE_REGEX = re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I)

WHATSAPP_DIRECT_DOMAINS = ("wa.me", "whatsapp.com")
WHATSAPP_HINT_KEYWORDS = ("whatsapp", "whats", "zap", "fale conosco", "fale com")

HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

NOPECHA_KEY = os.getenv("NOPECHA_KEY", "")
NOPECHA_PATH = os.getenv("NOPECHA_PATH", str(Path("./nopecha-extension").resolve()))
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
USER_DATA_DIR = os.getenv("BROWSER_USER_DATA", "/tmp/scraper-link-profile")

IA_PROVIDER = os.getenv("IA_PROVIDER", "groq").lower()
USE_IA_FALLBACK = os.getenv("USE_IA_FALLBACK", "true").lower() == "true"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-70b-instruct")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")

GROQ_CLIENT = None
OPENAI_CLIENT = None

if GROQ_API_KEY:
    try:
        from groq import Groq
        GROQ_CLIENT = Groq(api_key=GROQ_API_KEY)
        logger.info("✅ Groq configurado")
    except Exception as e:
        logger.warning(f"⚠️ Groq: {e}")

if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✅ OpenAI configurado")
    except Exception as e:
        logger.warning(f"⚠️ OpenAI: {e}")

USE_AIOGRAPI_FALLBACK = os.getenv("USE_AIOGRAPI_FALLBACK", "true").lower() == "true"
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")
SESSAO_INSTAGRAM_PATH = "/tmp/ig_session.json"

if not (HAS_AIOGRAPI and USE_AIOGRAPI_FALLBACK and IG_USERNAME and IG_PASSWORD):
    USE_AIOGRAPI_FALLBACK = False

DOMINIOS_IGNORAR = (
    "instagram.com", "facebook.com", "tiktok.com", "twitter.com", "x.com",
    "youtube.com", "linkedin.com", "spotify.com", "apple.com", "google.com",
)
MAX_LINKS_FALLBACK = 15

EMAILS_IGNORAR = {
    "example.com", "email.com", "domain.com", "sentry.io", "wixpress.com",
    "schema.org", "googleapis.com", "gstatic.com", "google.com", "facebook.com",
    "w3.org", "jquery.com", "cloudflare.com",
}

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)", re.I),
    "facebook":  re.compile(r"(?:https?://)?(?:www\.)?(?:facebook|fb)\.com/([a-zA-Z0-9.]+)", re.I),
    "linkedin":  re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9\-]+)", re.I),
    "twitter":   re.compile(r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]+)", re.I),
    "youtube":   re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/(?:c/|channel/|user/|@)?([a-zA-Z0-9_\-]+)", re.I),
    "tiktok":    re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9._]+)", re.I),
    "whatsapp":  re.compile(r"(?:https?://)?(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d+)", re.I),
}

# ============================================================
# MODELOS
# ============================================================

class ScrapeRequest(BaseModel):
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    link_bio: Optional[str] = None


class ScrapeResponse(BaseModel):
    status: str = "sem_resultado"
    telefone_encontrado: Optional[str] = None
    todos_os_numeros: List[str] = []
    fonte: Optional[str] = None
    fontes_verificadas: List[str] = []
    mensagem: str = ""
    erro: Optional[str] = None


class GoogleMapsPlace(BaseModel):
    nome: Optional[str] = None
    categoria: Optional[str] = None
    endereco: Optional[str] = None
    telefone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    total_reviews: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None
    url_maps: Optional[str] = None
    horario: Optional[str] = None
    status: Optional[str] = None
    emails: List[str] = []
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    whatsapp: Optional[str] = None
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None
    tiktok: Optional[str] = None


class GoogleMapsLeadRequest(BaseModel):
    nicho: str = Field(..., example="academia")
    cidade: str = Field(..., example="Curitiba")
    estado: str = Field(..., example="PR")
    bairro: Optional[str] = Field(None, example="Batel")
    quantidade: int = Field(20, ge=1, le=60)
    enrich_contacts: bool = True
    max_pages_per_site: int = Field(2, ge=1, le=5)


class GoogleMapsLeadResponse(BaseModel):
    status: str = "sucesso"
    query_usada: str = ""
    total_encontrados: int = 0
    nicho: str = ""
    cidade: str = ""
    estado: str = ""
    mensagem: str = ""
    lugares: List[GoogleMapsPlace] = []
    erro: Optional[str] = None


# ============================================================
# PLAYWRIGHT + NOPECHA
# ============================================================

@contextmanager
def browser_context():
    playwright = sync_playwright().start()
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-infobars",
    ]

    extension_loaded = False
    if Path(NOPECHA_PATH).exists() and (Path(NOPECHA_PATH) / "manifest.json").exists():
        args.extend([
            f"--disable-extensions-except={NOPECHA_PATH}",
            f"--load-extension={NOPECHA_PATH}",
        ])
        extension_loaded = True
        logger.info(f"🧩 NopeCHA carregada: {NOPECHA_PATH}")

    context = playwright.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=BROWSER_HEADLESS,
        channel="chromium",
        args=args,
        viewport={"width": 1366, "height": 768},
        locale="pt-BR",
        user_agent=HEADERS_NAVEGADOR["User-Agent"],
        ignore_default_args=["--enable-automation"],
    )

    if extension_loaded and NOPECHA_KEY:
        try:
            p = context.new_page()
            p.goto(f"https://nopecha.com/setup#{NOPECHA_KEY}", timeout=15000)
            p.wait_for_timeout(2000)
            p.close()
            logger.info("🔑 NopeCHA key configurada")
        except Exception as e:
            logger.warning(f"⚠️ NopeCHA key: {e}")

    try:
        yield context
    finally:
        context.close()
        playwright.stop()


def get_page_links_and_text(url: str, timeout: int = 25000) -> Tuple[List[dict], str, str]:
    with browser_context() as context:
        page = context.new_page()
        if HAS_STEALTH:
            try:
                stealth_sync(page)
            except Exception:
                pass

        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        page.wait_for_timeout(2500)

        links = page.eval_on_selector_all(
            "a",
            """els => els.map(e => ({
                href: e.href || '',
                text: (e.innerText || e.textContent || '').trim()
            }))"""
        ) or []

        texto = ""
        try:
            texto = page.inner_text("body")
        except Exception:
            pass

        try:
            metas = page.eval_on_selector_all(
                "meta[property='og:description'], meta[name='description']",
                "els => els.map(e => e.content || '').join(' ')"
            )
            if metas:
                texto = str(metas) + " " + texto
        except Exception:
            pass

        final_url = page.url
        page.close()
        return links, texto, final_url


def fetch_page_html(url: str, timeout: int = 20000) -> Tuple[str, str]:
    with browser_context() as context:
        page = context.new_page()
        if HAS_STEALTH:
            try:
                stealth_sync(page)
            except Exception:
                pass
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        page.wait_for_timeout(2000)
        html = page.content()
        final = page.url
        page.close()
        return html, final


# ============================================================
# AUXILIARES
# ============================================================

def somente_numeros(valor) -> str:
    if valor is None:
        return ""
    return "".join(c for c in str(valor) if c.isdigit())


def extrair_telefone_de_texto(texto: str) -> Optional[str]:
    if not texto:
        return None
    m = PHONE_REGEX.search(texto)
    return m.group(0) if m else None


def extrair_numero_de_url_whatsapp(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if "wa.me" in parsed.netloc:
        n = parsed.path.strip("/")
        return n if n.isdigit() else None
    if "whatsapp.com" in parsed.netloc:
        q = parse_qs(parsed.query)
        n = q.get("phone", [None])[0]
        if n:
            return re.sub(r"\D", "", n)
    return None


def eh_link_whatsapp_direto(url: str) -> bool:
    return any(d in url for d in WHATSAPP_DIRECT_DOMAINS)


def parece_botao_whatsapp(href: str, texto: str) -> bool:
    return any(kw in f"{href} {texto}".lower() for kw in WHATSAPP_HINT_KEYWORDS)


def extrair_numero_de_tel(href: str) -> Optional[str]:
    if not href.lower().startswith("tel:"):
        return None
    n = re.sub(r"\D", "", href)
    return n if n else None


def limpar_email(email: str) -> Optional[str]:
    email = email.lower().strip().rstrip(".")
    if any(ign in email for ign in EMAILS_IGNORAR):
        return None
    if email.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js")):
        return None
    return email


# ============================================================
# FALLBACK IA
# ============================================================

def extrair_com_ia(conteudo: str, origem: str = "página") -> Optional[str]:
    if not USE_IA_FALLBACK or not conteudo or len(conteudo) < 10:
        return None

    prompt = f"""Você é um extrator de WhatsApp.
Analise o conteúdo de {origem} e retorne APENAS o número brasileiro (ex: 5511999999999).
Se não encontrar, retorne: NENHUM

Conteúdo:
{conteudo[:2000]}"""

    if IA_PROVIDER == "groq" and GROQ_CLIENT:
        return _ia_groq(prompt)
    if IA_PROVIDER == "openai" and OPENAI_CLIENT:
        return _ia_openai(prompt)
    if IA_PROVIDER == "openrouter" and OPENROUTER_API_KEY:
        return _ia_openrouter(prompt)
    if IA_PROVIDER == "google" and GOOGLE_API_KEY:
        return _ia_google(prompt)

    if GROQ_CLIENT:
        return _ia_groq(prompt)
    if OPENAI_CLIENT:
        return _ia_openai(prompt)
    return None


def _ia_groq(prompt: str) -> Optional[str]:
    try:
        r = GROQ_CLIENT.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=20,
        )
        t = r.choices[0].message.content.strip()
        if t == "NENHUM":
            return None
        m = PHONE_REGEX.search(t)
        return m.group(0) if m else None
    except Exception as e:
        logger.warning(f"Groq: {e}")
        return None


def _ia_openai(prompt: str) -> Optional[str]:
    try:
        r = OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=20,
        )
        t = r.choices[0].message.content.strip()
        if t == "NENHUM":
            return None
        m = PHONE_REGEX.search(t)
        return m.group(0) if m else None
    except Exception as e:
        logger.warning(f"OpenAI: {e}")
        return None


def _ia_openrouter(prompt: str) -> Optional[str]:
    try:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1, "max_tokens": 20,
            },
            timeout=30,
        )
        if r.status_code != 200:
            return None
        t = r.json()["choices"][0]["message"]["content"].strip()
        if t == "NENHUM":
            return None
        m = PHONE_REGEX.search(t)
        return m.group(0) if m else None
    except Exception as e:
        logger.warning(f"OpenRouter: {e}")
        return None


def _ia_google(prompt: str) -> Optional[str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GOOGLE_MODEL)
        r = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 20},
        )
        t = r.text.strip()
        if t == "NENHUM":
            return None
        m = PHONE_REGEX.search(t)
        return m.group(0) if m else None
    except Exception as e:
        logger.warning(f"Google: {e}")
        return None


# ============================================================
# AIOGRAPI
# ============================================================

async def _aiograpi_async(username: str) -> Optional[str]:
    client = InstagramClient()
    if os.path.exists(SESSAO_INSTAGRAM_PATH):
        client.load_settings(SESSAO_INSTAGRAM_PATH)
    await client.login(IG_USERNAME, IG_PASSWORD)
    client.dump_settings(SESSAO_INSTAGRAM_PATH)
    info = await client.user_info_by_username(username)
    tel = getattr(info, "public_phone_number", None) or getattr(info, "contact_phone_number", None)
    return somente_numeros(str(tel)) if tel else None


def buscar_telefone_via_aiograpi(username: str) -> Optional[str]:
    if not USE_AIOGRAPI_FALLBACK:
        return None
    try:
        n = asyncio.run(_aiograpi_async(username))
        if n:
            logger.info(f"✅ aiograpi: {n}")
        return n
    except Exception as e:
        logger.warning(f"aiograpi @{username}: {e}")
        return None


# ============================================================
# RESOLUÇÃO DE LINKS
# ============================================================

def seguir_redirecionamentos(url: str) -> Optional[str]:
    for i in range(3):
        try:
            with httpx.Client(headers=HEADERS_NAVEGADOR, follow_redirects=True, timeout=15) as c:
                return str(c.get(url).url)
        except Exception:
            if i < 2:
                time.sleep(1 * (i + 1))
    return None


def resolver_link_ate_whatsapp(url: str) -> Optional[str]:
    if eh_link_whatsapp_direto(url):
        return extrair_numero_de_url_whatsapp(url)
    final = seguir_redirecionamentos(url)
    if final and eh_link_whatsapp_direto(final):
        return extrair_numero_de_url_whatsapp(final)
    try:
        _, final = fetch_page_html(url, timeout=12000)
        if final and eh_link_whatsapp_direto(final):
            return extrair_numero_de_url_whatsapp(final)
    except Exception:
        pass
    return None


# ============================================================
# E-MAIL + REDES SOCIAIS
# ============================================================

def extrair_contatos_do_html(html: str, base_url: str = "") -> Dict:
    resultado = {
        "emails": set(),
        "instagram": None, "facebook": None, "linkedin": None,
        "twitter": None, "youtube": None, "tiktok": None, "whatsapp": None,
    }

    for m in EMAIL_REGEX.findall(html):
        e = limpar_email(m)
        if e:
            resultado["emails"].add(e)

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
    urls = re.findall(r'(https?://[^\s"\'<>]+)', html, re.I)

    for link in hrefs + urls:
        link = link.strip()
        if not link.startswith("http") and base_url:
            link = urljoin(base_url, link)
        if not link.startswith("http"):
            continue

        for rede, pattern in SOCIAL_PATTERNS.items():
            if resultado[rede]:
                continue
            m = pattern.search(link)
            if not m:
                continue
            if rede == "whatsapp":
                resultado[rede] = re.sub(r"\D", "", m.group(1))
            elif rede == "instagram":
                resultado[rede] = f"https://instagram.com/{m.group(1)}"
            elif rede == "facebook":
                resultado[rede] = f"https://facebook.com/{m.group(1)}"
            elif rede == "twitter":
                resultado[rede] = f"https://x.com/{m.group(1)}"
            elif rede == "tiktok":
                resultado[rede] = f"https://tiktok.com/@{m.group(1)}"
            else:
                resultado[rede] = link.split("?")[0]

    resultado["emails"] = sorted(list(resultado["emails"]))
    return resultado


def enriquecer_com_website(website: str, max_pages: int = 2) -> Dict:
    contatos = {
        "emails": [], "instagram": None, "facebook": None, "whatsapp": None,
        "linkedin": None, "twitter": None, "youtube": None, "tiktok": None,
    }
    if not website or not website.startswith("http"):
        return contatos

    paths = ["", "/contato", "/contact", "/sobre", "/about"][:max_pages]

    try:
        with browser_context() as context:
            page = context.new_page()
            if HAS_STEALTH:
                try:
                    stealth_sync(page)
                except Exception:
                    pass

            for path in paths:
                try:
                    url = website.rstrip("/") + path
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(1500)
                    html = page.content()
                    extra = extrair_contatos_do_html(html, base_url=website)

                    for e in extra["emails"]:
                        if e not in contatos["emails"]:
                            contatos["emails"].append(e)
                    for rede in ["instagram", "facebook", "linkedin", "twitter", "youtube", "tiktok", "whatsapp"]:
                        if not contatos[rede] and extra.get(rede):
                            contatos[rede] = extra[rede]

                    if contatos["emails"] and contatos["instagram"] and contatos["facebook"]:
                        break
                except Exception:
                    continue
            page.close()
    except Exception as e:
        logger.warning(f"Enriquecimento {website}: {e}")

    return contatos


# ============================================================
# INSTAGRAM / FACEBOOK / LINK-BIO
# ============================================================

def buscar_whatsapp_em_link_bio(url: str) -> Optional[str]:
    try:
        links, texto, _ = get_page_links_and_text(url, timeout=20000)

        for item in links:
            n = extrair_numero_de_tel(item.get("href", ""))
            if n:
                return n

        candidatos = [
            item["href"] for item in links
            if parece_botao_whatsapp(item.get("href", ""), item.get("text", ""))
        ]
        candidatos.sort(key=lambda h: 0 if eh_link_whatsapp_direto(h) else 1)

        for href in candidatos:
            n = resolver_link_ate_whatsapp(href)
            if n:
                return n

        outros = [
            item["href"] for item in links
            if item.get("href", "").startswith("http")
            and item["href"] not in candidatos
            and not any(d in item["href"] for d in DOMINIOS_IGNORAR)
        ][:MAX_LINKS_FALLBACK]

        for href in outros:
            n = resolver_link_ate_whatsapp(href)
            if n:
                return n

        n = extrair_telefone_de_texto(texto)
        if n:
            return n
        return extrair_com_ia(texto, "link-in-bio")
    except Exception as e:
        logger.warning(f"link-bio {url}: {e}")
        return None


def buscar_telefone_instagram(link: str) -> Optional[str]:
    try:
        if "instagram.com" in link:
            path = urlparse(link).path.strip("/")
            username = path.split("/")[-1] if path else link.lstrip("@")
        else:
            username = link.lstrip("@")

        url = f"https://www.instagram.com/{username}/"
        links, texto, _ = get_page_links_and_text(url, timeout=25000)

        n = extrair_telefone_de_texto(texto)
        if n:
            return n

        for item in links:
            href = item.get("href", "")
            if "wa.me" in href or "whatsapp.com" in href:
                n = extrair_numero_de_url_whatsapp(href)
                if n:
                    return n

        for item in links:
            href = item.get("href", "")
            if any(d in href for d in ("linktr.ee", "beacons.ai", "bio.link", "linkin.bio")):
                n = buscar_whatsapp_em_link_bio(href)
                if n:
                    return n

        for item in links:
            href = item.get("href", "")
            if parece_botao_whatsapp(href, item.get("text", "")):
                if href.startswith("http"):
                    n = resolver_link_ate_whatsapp(href)
                    if n:
                        return n
                elif href.startswith("tel:"):
                    n = extrair_numero_de_tel(href)
                    if n:
                        return n

        n = buscar_telefone_via_aiograpi(username)
        if n:
            return n
        return extrair_com_ia(texto, "Instagram")
    except Exception as e:
        logger.warning(f"Instagram {link}: {e}")
        return None


def buscar_telefone_facebook(link: str) -> Optional[str]:
    try:
        links, texto, _ = get_page_links_and_text(link, timeout=20000)
        n = extrair_telefone_de_texto(texto)
        if n:
            return n
        for item in links:
            href = item.get("href", "")
            if "wa.me" in href or "whatsapp.com" in href:
                n = extrair_numero_de_url_whatsapp(href)
                if n:
                    return n
            if href.startswith("tel:"):
                n = extrair_numero_de_tel(href)
                if n:
                    return n
        return extrair_com_ia(texto, "Facebook")
    except Exception as e:
        logger.warning(f"Facebook {link}: {e}")
        return None


def buscar_telefone_em_site_generico(url: str) -> Optional[str]:
    try:
        links, texto, _ = get_page_links_and_text(url, timeout=20000)
        for item in links:
            n = extrair_numero_de_tel(item.get("href", ""))
            if n:
                return n
        for item in links:
            href = item.get("href", "")
            if "wa.me" in href or "whatsapp.com" in href:
                n = extrair_numero_de_url_whatsapp(href)
                if n:
                    return n
        n = extrair_telefone_de_texto(texto)
        if n:
            return n
        return extrair_com_ia(texto, "site")
    except Exception as e:
        logger.warning(f"Site {url}: {e}")
        return None


# ============================================================
# GOOGLE MAPS
# ============================================================

def extrair_coordenadas_da_url(url: str) -> Tuple[Optional[float], Optional[float]]:
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def extrair_place_id(url: str) -> Optional[str]:
    m = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"place_id[=:]([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def montar_query_busca(
    nicho: str,
    cidade: str,
    estado: str,
    bairro: Optional[str] = None,
) -> str:
    """Monta a busca livremente com o que o usuário digitou."""
    partes = [nicho.strip()]
    if bairro:
        partes.append(f"em {bairro.strip()}")
    partes.append(f"em {cidade.strip()}")
    partes.append(estado.strip())
    return " ".join(partes)


def scrape_google_maps(
    query: str,
    max_results: int = 20,
    enrich_contacts: bool = True,
    max_pages_per_site: int = 2,
) -> List[Dict]:
    resultados = []

    with browser_context() as context:
        page = context.new_page()
        if HAS_STEALTH:
            try:
                stealth_sync(page)
            except Exception:
                pass

        search_url = f"https://www.google.com/maps/search/{quote_plus(query)}?hl=pt-BR"
        logger.info(f"🗺️ Google Maps: {query}")
        page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000 + random.randint(400, 1200))

        try:
            for sel in [
                'button:has-text("Aceitar tudo")',
                'button:has-text("Accept all")',
                'button:has-text("Concordo")',
            ]:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1500):
                    btn.click()
                    page.wait_for_timeout(800)
                    break
        except Exception:
            pass

        try:
            page.wait_for_selector('div[role="feed"]', timeout=15000)
        except Exception:
            logger.warning("⚠️ Feed do Maps não apareceu (CAPTCHA/bloqueio?)")
            page.close()
            return resultados

        feed = page.locator('div[role="feed"]').first
        vistos = set()
        sem_novo = 0

        while len(resultados) < max_results and sem_novo < 6:
            cards = page.locator('div[role="feed"] a[href*="/maps/place/"]').all()
            novos = 0

            for card in cards:
                if len(resultados) >= max_results:
                    break
                try:
                    href = card.get_attribute("href") or ""
                    if not href or href in vistos:
                        continue
                    vistos.add(href)

                    nome = card.get_attribute("aria-label") or ""
                    if not nome:
                        try:
                            nome = card.inner_text().split("\n")[0].strip()
                        except Exception:
                            continue
                    if len(nome) < 2:
                        continue

                    card.click()
                    page.wait_for_timeout(1600 + random.randint(200, 700))

                    dados = {
                        "nome": nome,
                        "categoria": None,
                        "endereco": None,
                        "telefone": None,
                        "website": None,
                        "rating": None,
                        "total_reviews": None,
                        "latitude": None,
                        "longitude": None,
                        "place_id": None,
                        "url_maps": page.url,
                        "horario": None,
                        "status": None,
                        "emails": [],
                        "instagram": None,
                        "facebook": None,
                        "whatsapp": None,
                        "linkedin": None,
                        "twitter": None,
                        "youtube": None,
                        "tiktok": None,
                    }

                    lat, lng = extrair_coordenadas_da_url(page.url)
                    dados["latitude"] = lat
                    dados["longitude"] = lng
                    dados["place_id"] = extrair_place_id(page.url)

                    try:
                        rt = page.locator('div[role="main"] span[aria-hidden="true"]').first.inner_text(timeout=1200)
                        if re.match(r"^\d+[.,]\d+$", rt.replace(",", ".")):
                            dados["rating"] = float(rt.replace(",", "."))
                    except Exception:
                        pass

                    try:
                        aria = (
                            page.locator(
                                'div[role="main"] button[aria-label*="avaliaç"], '
                                'div[role="main"] button[aria-label*="review"]'
                            )
                            .first.get_attribute("aria-label")
                            or ""
                        )
                        m = re.search(r"([\d\.\,]+)", aria.replace(".", "").replace(",", ""))
                        if m:
                            dados["total_reviews"] = int(m.group(1))
                    except Exception:
                        pass

                    try:
                        dados["endereco"] = (
                            page.locator(
                                'button[data-item-id="address"], '
                                'button[aria-label*="Endereço"], '
                                'button[aria-label*="Address"]'
                            )
                            .first.inner_text(timeout=1200)
                            .strip()
                        )
                    except Exception:
                        pass

                    try:
                        tel = (
                            page.locator(
                                'button[data-item-id*="phone"], '
                                'button[aria-label*="Telefone"], '
                                'button[aria-label*="Phone"]'
                            )
                            .first.inner_text(timeout=1200)
                            .strip()
                        )
                        dados["telefone"] = re.sub(r"[^\d\+]", "", tel) or tel
                    except Exception:
                        pass

                    try:
                        dados["website"] = page.locator(
                            'a[data-item-id="authority"], '
                            'a[aria-label*="Website"], '
                            'a[aria-label*="Site"]'
                        ).first.get_attribute("href")
                    except Exception:
                        pass

                    try:
                        dados["categoria"] = (
                            page.locator('div[role="main"] button[jsaction*="category"]')
                            .first.inner_text(timeout=800)
                            .strip()
                        )
                    except Exception:
                        pass

                    try:
                        dados["horario"] = (
                            page.locator(
                                'div[role="main"] [aria-label*="horário"], '
                                'div[role="main"] [aria-label*="Hours"]'
                            )
                            .first.inner_text(timeout=800)
                            .strip()
                        )
                    except Exception:
                        pass

                    if enrich_contacts and dados.get("website"):
                        logger.info(f"🔍 Enriquecendo: {dados['website']}")
                        c = enriquecer_com_website(dados["website"], max_pages=max_pages_per_site)
                        dados["emails"] = c["emails"]
                        dados["instagram"] = c["instagram"]
                        dados["facebook"] = c["facebook"]
                        dados["whatsapp"] = c["whatsapp"] or dados.get("telefone")
                        dados["linkedin"] = c["linkedin"]
                        dados["twitter"] = c["twitter"]
                        dados["youtube"] = c["youtube"]
                        dados["tiktok"] = c["tiktok"]
                    else:
                        dados["whatsapp"] = dados.get("telefone")

                    resultados.append(dados)
                    novos += 1
                    logger.info(f"✅ [{len(resultados)}] {dados['nome']} | {dados.get('telefone')}")

                except Exception as e:
                    logger.debug(f"Card erro: {e}")
                    continue

            if novos == 0:
                sem_novo += 1
            else:
                sem_novo = 0

            try:
                feed.evaluate("el => el.scrollTop += 900")
                page.wait_for_timeout(1100 + random.randint(200, 600))
            except Exception:
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(1400)

        page.close()

    return resultados


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extrair-telefone", response_model=ScrapeResponse)
def extrair_telefone(req: ScrapeRequest):
    fontes = []
    try:
        if req.link_bio:
            fontes.append("link_bio")
            n = buscar_whatsapp_em_link_bio(req.link_bio)
            if n:
                return ScrapeResponse(
                    status="sucesso",
                    telefone_encontrado=n,
                    todos_os_numeros=[n],
                    fonte="link_bio",
                    fontes_verificadas=fontes,
                    mensagem=f"Telefone: {n}",
                )

        if req.instagram:
            fontes.append("instagram")
            n = buscar_telefone_instagram(req.instagram)
            if n:
                return ScrapeResponse(
                    status="sucesso",
                    telefone_encontrado=n,
                    todos_os_numeros=[n],
                    fonte="instagram",
                    fontes_verificadas=fontes,
                    mensagem=f"Telefone: {n}",
                )

        if req.facebook:
            fontes.append("facebook")
            n = buscar_telefone_facebook(req.facebook)
            if n:
                return ScrapeResponse(
                    status="sucesso",
                    telefone_encontrado=n,
                    todos_os_numeros=[n],
                    fonte="facebook",
                    fontes_verificadas=fontes,
                    mensagem=f"Telefone: {n}",
                )

        return ScrapeResponse(
            status="sem_resultado",
            fontes_verificadas=fontes,
            mensagem="Nenhum telefone encontrado",
        )
    except Exception as e:
        logger.error(f"Erro: {e}")
        return ScrapeResponse(
            status="erro",
            fontes_verificadas=fontes,
            mensagem="Erro",
            erro=str(e),
        )


@app.post("/extrair-telefone-site")
def extrair_telefone_site(req: dict):
    url = req.get("url")
    if not url:
        return {"status": "erro", "mensagem": "url obrigatória", "telefone_encontrado": None}
    n = buscar_telefone_em_site_generico(url)
    if n:
        return {
            "status": "sucesso",
            "telefone_encontrado": n,
            "fonte": "site_generico",
            "mensagem": f"Telefone: {n}",
        }
    return {
        "status": "sem_resultado",
        "telefone_encontrado": None,
        "fonte": "site_generico",
        "mensagem": "Nenhum telefone",
    }


@app.post("/gerar-leads", response_model=GoogleMapsLeadResponse)
def gerar_leads(req: GoogleMapsLeadRequest):
    """
    Gera leads do Google Maps.
    Você escolhe livremente nicho, cidade e estado.

    Exemplo:
    {
      "nicho": "academia",
      "cidade": "Curitiba",
      "estado": "PR",
      "quantidade": 20,
      "enrich_contacts": true
    }
    """
    try:
        if not req.nicho or len(req.nicho.strip()) < 2:
            return GoogleMapsLeadResponse(
                status="erro",
                mensagem="Informe o nicho",
                erro="nicho obrigatório",
            )

        if not req.cidade or len(req.cidade.strip()) < 2:
            return GoogleMapsLeadResponse(
                status="erro",
                mensagem="Informe a cidade",
                erro="cidade obrigatória",
            )

        if not req.estado or len(req.estado.strip()) < 2:
            return GoogleMapsLeadResponse(
                status="erro",
                mensagem="Informe o estado",
                erro="estado obrigatório",
            )

        quantidade = max(1, min(req.quantidade, 60))

        query = montar_query_busca(
            nicho=req.nicho,
            cidade=req.cidade,
            estado=req.estado,
            bairro=req.bairro,
        )

        logger.info(f"🎯 Leads → {query} | qtd={quantidade}")

        raw = scrape_google_maps(
            query=query,
            max_results=quantidade,
            enrich_contacts=req.enrich_contacts,
            max_pages_per_site=req.max_pages_per_site,
        )

        lugares = [GoogleMapsPlace(**item) for item in raw]

        return GoogleMapsLeadResponse(
            status="sucesso" if lugares else "sem_resultado",
            query_usada=query,
            total_encontrados=len(lugares),
            nicho=req.nicho,
            cidade=req.cidade,
            estado=req.estado,
            lugares=lugares,
            mensagem=f"Encontrados {len(lugares)} leads de '{query}'",
        )

    except Exception as e:
        logger.error(f"❌ gerar-leads: {e}")
        return GoogleMapsLeadResponse(
            status="erro",
            nicho=req.nicho,
            cidade=req.cidade,
            estado=req.estado,
            mensagem="Erro ao gerar leads",
            erro=str(e),
        )
