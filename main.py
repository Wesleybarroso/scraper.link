"""
SCRAPER DE CONTATOS - Extrator de Telefones/WhatsApp
====================================================
Versão com Playwright + NopeCHA Extension

Funcionalidades:
- Extrai telefones com regex brasileiro
- Resolve encurtadores (HTTP + JavaScript)
- Busca em Instagram, Facebook e Link-in-bio
- Fallback via API privada do Instagram (aiograpi)
- Fallback via IA (Groq / OpenAI / OpenRouter / Google)
- API REST com FastAPI
- Playwright + extensão NopeCHA para CAPTCHAs
"""

import re
import logging
import time
import os
import asyncio
from pathlib import Path
from typing import Optional, List, Tuple
from urllib.parse import urlparse, parse_qs
from contextlib import contextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from aiograpi import Client as InstagramClient

from playwright.sync_api import sync_playwright, BrowserContext, Page

# Stealth opcional
try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper-leads")

app = FastAPI(title="Scraper de telefone - Leads (Playwright + NopeCHA)")

# ==================== CONFIGURAÇÕES ====================

PHONE_REGEX = re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}")

WHATSAPP_DIRECT_DOMAINS = ("wa.me", "whatsapp.com")
WHATSAPP_HINT_KEYWORDS = ("whatsapp", "whats", "zap", "fale conosco", "fale com")

HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

# NopeCHA + Playwright
NOPECHA_KEY = os.getenv("NOPECHA_KEY", "")
NOPECHA_PATH = os.getenv("NOPECHA_PATH", str(Path("./nopecha-extension").resolve()))
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
USER_DATA_DIR = os.getenv("BROWSER_USER_DATA", "/tmp/scraper-link-profile")

# IA
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
        logger.info("✅ Groq API configurada")
    except Exception as e:
        logger.warning(f"⚠️ Falha ao configurar Groq: {e}")

if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✅ OpenAI API configurada")
    except Exception as e:
        logger.warning(f"⚠️ Falha ao configurar OpenAI: {e}")

if USE_IA_FALLBACK:
    logger.info(f"🤖 Provedor de IA: {IA_PROVIDER.upper()}")
else:
    logger.info("🔇 Fallback IA desativado")

# aiograpi
USE_AIOGRAPI_FALLBACK = os.getenv("USE_AIOGRAPI_FALLBACK", "true").lower() == "true"
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")
SESSAO_INSTAGRAM_PATH = "/tmp/ig_session.json"

if USE_AIOGRAPI_FALLBACK and IG_USERNAME and IG_PASSWORD:
    logger.info("📷 Fallback aiograpi configurado")
else:
    USE_AIOGRAPI_FALLBACK = False
    logger.info("🔇 Fallback aiograpi desativado")

DOMINIOS_IGNORAR_NO_FALLBACK = (
    "instagram.com", "facebook.com", "tiktok.com", "twitter.com", "x.com",
    "youtube.com", "linkedin.com", "spotify.com", "apple.com",
)
MAX_LINKS_FALLBACK = 15

# ==================== MODELOS ====================

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


# ==================== PLAYWRIGHT + NOPECHA ====================

@contextmanager
def browser_context():
    """
    Context manager que abre um browser persistente com:
    - Stealth básico
    - Extensão NopeCHA (se a pasta existir)
    """
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
        logger.info(f"🧩 Extensão NopeCHA carregada de: {NOPECHA_PATH}")
    else:
        logger.info("ℹ️ Pasta NopeCHA não encontrada – rodando sem extensão")

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

    # Configura chave do NopeCHA uma vez por contexto
    if extension_loaded and NOPECHA_KEY:
        try:
            setup_page = context.new_page()
            setup_page.goto(f"https://nopecha.com/setup#{NOPECHA_KEY}", timeout=15000)
            setup_page.wait_for_timeout(2000)
            setup_page.close()
            logger.info("🔑 Chave NopeCHA configurada")
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível configurar NopeCHA key: {e}")

    try:
        yield context
    finally:
        context.close()
        playwright.stop()


def fetch_page(url: str, timeout: int = 25000) -> Tuple[str, str]:
    """
    Abre a URL com Playwright (+ NopeCHA se disponível).
    Retorna (html, url_final)
    """
    with browser_context() as context:
        page = context.new_page()
        if HAS_STEALTH:
            try:
                stealth_sync(page)
            except Exception:
                pass

        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        # Tempo para a extensão NopeCHA resolver CAPTCHA se aparecer
        page.wait_for_timeout(2500)

        html = page.content()
        final_url = page.url
        page.close()
        return html, final_url


def get_page_links_and_text(url: str, timeout: int = 25000) -> Tuple[List[dict], str, str]:
    """
    Abre a página e retorna:
    - lista de {href, text}
    - texto completo visível
    - url final
    """
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
        )

        # texto visível
        texto = page.inner_text("body") if page.query_selector("body") else ""

        # meta descriptions
        metas = page.eval_on_selector_all(
            "meta[property='og:description'], meta[name='description']",
            "els => els.map(e => e.content || '').join(' ')"
        )
        if metas:
            texto = metas + " " + texto

        final_url = page.url
        page.close()
        return links or [], texto, final_url


# ==================== FUNÇÕES AUXILIARES ====================

def somenteNumeros(valor) -> str:
    if valor is None:
        return ""
    return "".join(c for c in str(valor) if c.isdigit())


def extrair_telefone_de_texto(texto: str) -> Optional[str]:
    if not texto:
        return None
    match = PHONE_REGEX.search(texto)
    return match.group(0) if match else None


def extrair_numero_de_url_whatsapp(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if "wa.me" in parsed.netloc:
        numero = parsed.path.strip("/")
        return numero if numero.isdigit() else None
    if "whatsapp.com" in parsed.netloc:
        query = parse_qs(parsed.query)
        numero = query.get("phone", [None])[0]
        if numero:
            return re.sub(r"\D", "", numero)
    return None


def eh_link_whatsapp_direto(url: str) -> bool:
    return any(dominio in url for dominio in WHATSAPP_DIRECT_DOMAINS)


def parece_botao_whatsapp(href: str, texto_do_link: str) -> bool:
    alvo = f"{href} {texto_do_link}".lower()
    return any(kw in alvo for kw in WHATSAPP_HINT_KEYWORDS)


def extrair_numero_de_tel(href: str) -> Optional[str]:
    if not href.lower().startswith("tel:"):
        return None
    numero = re.sub(r"\D", "", href)
    return numero if numero else None


# ==================== FALLBACK IA ====================

def extrair_com_ia(conteudo: str, origem: str = "página") -> Optional[str]:
    if not USE_IA_FALLBACK or not conteudo or len(conteudo) < 10:
        return None

    conteudo_limitado = conteudo[:2000]
    prompt = f"""Você é um extrator de dados especializado em extrair números de WhatsApp.

Analise o seguinte conteúdo de um perfil {origem} e extraia APENAS o número de WhatsApp no formato brasileiro.

Conteúdo:
{conteudo_limitado}

Instruções:
1. Procure por números de WhatsApp em qualquer formato
2. Retorne APENAS o número (ex: 5511999999999 ou +5511999999999)
3. Se não encontrar WhatsApp, retorne: NENHUM
4. Não inclua explicações, retorne apenas o número ou NENHUM"""

    if IA_PROVIDER == "groq" and GROQ_CLIENT:
        return _extrair_com_groq(prompt)
    elif IA_PROVIDER == "openai" and OPENAI_CLIENT:
        return _extrair_com_openai(prompt)
    elif IA_PROVIDER == "openrouter" and OPENROUTER_API_KEY:
        return _extrair_com_openrouter(prompt)
    elif IA_PROVIDER == "google" and GOOGLE_API_KEY:
        return _extrair_com_google(prompt)

    # fallback automático
    if GROQ_CLIENT:
        return _extrair_com_groq(prompt)
    if OPENAI_CLIENT:
        return _extrair_com_openai(prompt)
    if OPENROUTER_API_KEY:
        return _extrair_com_openrouter(prompt)
    if GOOGLE_API_KEY:
        return _extrair_com_google(prompt)
    return None


def _extrair_com_groq(prompt: str) -> Optional[str]:
    try:
        response = GROQ_CLIENT.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=20,
        )
        resultado = response.choices[0].message.content.strip()
        if resultado == "NENHUM" or not resultado:
            return None
        match = PHONE_REGEX.search(resultado)
        if match:
            logger.info(f"✅ IA Groq extraiu: {match.group(0)}")
            return match.group(0)
    except Exception as e:
        logger.warning(f"⚠️ Falha Groq: {e}")
    return None


def _extrair_com_openai(prompt: str) -> Optional[str]:
    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=20,
        )
        resultado = response.choices[0].message.content.strip()
        if resultado == "NENHUM" or not resultado:
            return None
        match = PHONE_REGEX.search(resultado)
        if match:
            logger.info(f"✅ IA OpenAI extraiu: {match.group(0)}")
            return match.group(0)
    except Exception as e:
        logger.warning(f"⚠️ Falha OpenAI: {e}")
    return None


def _extrair_com_openrouter(prompt: str) -> Optional[str]:
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://scraper.link",
            "X-Title": "Scraper de Telefones",
        }
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 20,
        }
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if response.status_code != 200:
            return None
        resultado = response.json()["choices"][0]["message"]["content"].strip()
        if resultado == "NENHUM" or not resultado:
            return None
        match = PHONE_REGEX.search(resultado)
        if match:
            logger.info(f"✅ IA OpenRouter extraiu: {match.group(0)}")
            return match.group(0)
    except Exception as e:
        logger.warning(f"⚠️ Falha OpenRouter: {e}")
    return None


def _extrair_com_google(prompt: str) -> Optional[str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GOOGLE_MODEL)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=20,
            )
        )
        resultado = response.text.strip()
        if resultado == "NENHUM" or not resultado:
            return None
        match = PHONE_REGEX.search(resultado)
        if match:
            logger.info(f"✅ IA Google extraiu: {match.group(0)}")
            return match.group(0)
    except Exception as e:
        logger.warning(f"⚠️ Falha Google: {e}")
    return None


# ==================== AIOGRAPI ====================

async def _buscar_telefone_via_aiograpi_async(username: str) -> Optional[str]:
    cliente = InstagramClient()
    if os.path.exists(SESSAO_INSTAGRAM_PATH):
        cliente.load_settings(SESSAO_INSTAGRAM_PATH)
    await cliente.login(IG_USERNAME, IG_PASSWORD)
    cliente.dump_settings(SESSAO_INSTAGRAM_PATH)
    info = await cliente.user_info_by_username(username)
    telefone = (
        getattr(info, "public_phone_number", None)
        or getattr(info, "contact_phone_number", None)
    )
    return somenteNumeros(str(telefone)) if telefone else None


def buscar_telefone_via_aiograpi(username: str) -> Optional[str]:
    if not USE_AIOGRAPI_FALLBACK:
        return None
    try:
        numero = asyncio.run(_buscar_telefone_via_aiograpi_async(username))
        if numero:
            logger.info(f"✅ aiograpi extraiu: {numero}")
        return numero
    except Exception as e:
        logger.warning(f"⚠️ Falha aiograpi @{username}: {e}")
        return None


# ==================== RESOLUÇÃO DE LINKS ====================

def seguir_redirecionamentos(url: str) -> Optional[str]:
    for tentativa in range(3):
        try:
            with httpx.Client(headers=HEADERS_NAVEGADOR, follow_redirects=True, timeout=15) as client:
                resp = client.get(url)
                return str(resp.url)
        except Exception as e:
            if tentativa < 2:
                time.sleep(1 * (tentativa + 1))
            else:
                logger.warning(f"Falha redirect HTTP {url}: {e}")
    return None


def seguir_redirecionamento_via_browser(url: str) -> Optional[str]:
    try:
        _, final_url = fetch_page(url, timeout=15000)
        return final_url
    except Exception as e:
        logger.warning(f"Falha redirect browser {url}: {e}")
        return None


def resolver_link_ate_whatsapp(url_inicial: str) -> Optional[str]:
    if eh_link_whatsapp_direto(url_inicial):
        return extrair_numero_de_url_whatsapp(url_inicial)

    url_final = seguir_redirecionamentos(url_inicial)
    if url_final and eh_link_whatsapp_direto(url_final):
        return extrair_numero_de_url_whatsapp(url_final)

    url_final_browser = seguir_redirecionamento_via_browser(url_inicial)
    if url_final_browser and eh_link_whatsapp_direto(url_final_browser):
        return extrair_numero_de_url_whatsapp(url_final_browser)

    return None


# ==================== BUSCAS PRINCIPAIS ====================

def buscar_whatsapp_em_link_bio(url: str) -> Optional[str]:
    try:
        links, texto, _ = get_page_links_and_text(url, timeout=20000)

        # 1) tel:
        for item in links:
            numero = extrair_numero_de_tel(item.get("href", ""))
            if numero:
                return numero

        # 2) candidatos com palavra-chave
        candidatos = [
            item["href"] for item in links
            if parece_botao_whatsapp(item.get("href", ""), item.get("text", ""))
        ]
        candidatos.sort(key=lambda h: 0 if eh_link_whatsapp_direto(h) else 1)

        for href in candidatos:
            numero = resolver_link_ate_whatsapp(href)
            if numero:
                return numero

        # 3) fallback genérico
        outros = [
            item["href"] for item in links
            if item.get("href", "").startswith("http")
            and item["href"] not in candidatos
            and not any(d in item["href"] for d in DOMINIOS_IGNORAR_NO_FALLBACK)
        ][:MAX_LINKS_FALLBACK]

        for href in outros:
            numero = resolver_link_ate_whatsapp(href)
            if numero:
                return numero

        # 4) texto + IA
        telefone = extrair_telefone_de_texto(texto)
        if telefone:
            return telefone

        return extrair_com_ia(texto, "link-in-bio")
    except Exception as e:
        logger.warning(f"Falha link-bio ({url}): {e}")
        return None


def buscar_telefone_instagram(link: str) -> Optional[str]:
    try:
        if "instagram.com" in link:
            parsed = urlparse(link)
            caminho = parsed.path.strip("/")
            username = caminho.split("/")[-1] if caminho else link.lstrip("@")
        else:
            username = link.lstrip("@")

        url = f"https://www.instagram.com/{username}/"
        links, texto, _ = get_page_links_and_text(url, timeout=25000)

        # 1) texto / meta
        telefone = extrair_telefone_de_texto(texto)
        if telefone:
            return telefone

        # 2) links wa.me / whatsapp
        for item in links:
            href = item.get("href", "")
            if "wa.me" in href or "whatsapp.com" in href:
                numero = extrair_numero_de_url_whatsapp(href)
                if numero:
                    return numero

        # 3) link-in-bio
        bio_links = [
            item["href"] for item in links
            if any(d in item.get("href", "") for d in (
                "linktr.ee", "beacons.ai", "bio.link", "linkin.bio"
            ))
        ]
        for bio in bio_links:
            numero = buscar_whatsapp_em_link_bio(bio)
            if numero:
                return numero

        # 4) candidatos com palavras-chave
        candidatos = [
            item["href"] for item in links
            if parece_botao_whatsapp(item.get("href", ""), item.get("text", ""))
            or "contato" in item.get("text", "").lower()
            or "message" in item.get("text", "").lower()
        ]
        for href in candidatos:
            if href.startswith("http"):
                numero = resolver_link_ate_whatsapp(href)
                if numero:
                    return numero
            elif href.startswith("tel:"):
                numero = extrair_numero_de_tel(href)
                if numero:
                    return numero

        # 5) aiograpi
        numero = buscar_telefone_via_aiograpi(username)
        if numero:
            return numero

        # 6) IA
        return extrair_com_ia(texto, "Instagram")
    except Exception as e:
        logger.warning(f"Falha Instagram ({link}): {e}")
        return None


def buscar_telefone_facebook(link: str) -> Optional[str]:
    try:
        links, texto, _ = get_page_links_and_text(link, timeout=20000)

        telefone = extrair_telefone_de_texto(texto)
        if telefone:
            return telefone

        for item in links:
            href = item.get("href", "")
            if "wa.me" in href or "whatsapp.com" in href:
                numero = extrair_numero_de_url_whatsapp(href)
                if numero:
                    return numero
            if href.startswith("tel:"):
                numero = extrair_numero_de_tel(href)
                if numero:
                    return numero

        return extrair_com_ia(texto, "Facebook")
    except Exception as e:
        logger.warning(f"Falha Facebook ({link}): {e}")
        return None


def buscar_telefone_em_site_generico(url: str) -> Optional[str]:
    try:
        logger.info(f"🔍 Buscando em site genérico: {url}")
        links, texto, _ = get_page_links_and_text(url, timeout=20000)

        for item in links:
            href = item.get("href", "")
            numero = extrair_numero_de_tel(href)
            if numero:
                return numero

        for item in links:
            href = item.get("href", "")
            if "wa.me" in href or "whatsapp.com" in href:
                numero = extrair_numero_de_url_whatsapp(href)
                if numero:
                    return numero

        telefone = extrair_telefone_de_texto(texto)
        if telefone:
            return telefone

        return extrair_com_ia(texto, "site")
    except Exception as e:
        logger.warning(f"Falha site genérico ({url}): {e}")
        return None


# ==================== ENDPOINTS ====================

@app.post("/extrair-telefone", response_model=ScrapeResponse)
def extrair_telefone(req: ScrapeRequest):
    fontes_verificadas = []

    try:
        if req.link_bio:
            fontes_verificadas.append("link_bio")
            numero = buscar_whatsapp_em_link_bio(req.link_bio)
            if numero:
                return ScrapeResponse(
                    status="sucesso",
                    telefone_encontrado=numero,
                    todos_os_numeros=[numero],
                    fonte="link_bio",
                    fontes_verificadas=fontes_verificadas,
                    mensagem=f"Telefone encontrado no link-in-bio: {numero}",
                )

        if req.instagram:
            fontes_verificadas.append("instagram")
            telefone = buscar_telefone_instagram(req.instagram)
            if telefone:
                return ScrapeResponse(
                    status="sucesso",
                    telefone_encontrado=telefone,
                    todos_os_numeros=[telefone],
                    fonte="instagram",
                    fontes_verificadas=fontes_verificadas,
                    mensagem=f"Telefone encontrado no Instagram: {telefone}",
                )

        if req.facebook:
            fontes_verificadas.append("facebook")
            telefone = buscar_telefone_facebook(req.facebook)
            if telefone:
                return ScrapeResponse(
                    status="sucesso",
                    telefone_encontrado=telefone,
                    todos_os_numeros=[telefone],
                    fonte="facebook",
                    fontes_verificadas=fontes_verificadas,
                    mensagem=f"Telefone encontrado no Facebook: {telefone}",
                )

        return ScrapeResponse(
            status="sem_resultado",
            fontes_verificadas=fontes_verificadas,
            mensagem="Nenhum telefone encontrado nas fontes informadas",
        )

    except Exception as e:
        logger.error(f"❌ Erro geral: {e}")
        return ScrapeResponse(
            status="erro",
            fontes_verificadas=fontes_verificadas,
            mensagem="Erro ao processar a requisição",
            erro=str(e),
        )


@app.post("/extrair-telefone-site")
def extrair_telefone_site(req: dict):
    url = req.get("url")
    if not url:
        return {
            "status": "erro",
            "mensagem": "Parâmetro 'url' é obrigatório",
            "telefone_encontrado": None,
        }

    telefone = buscar_telefone_em_site_generico(url)
    if telefone:
        return {
            "status": "sucesso",
            "telefone_encontrado": telefone,
            "todos_os_numeros": [telefone],
            "fonte": "site_generico",
            "mensagem": f"Telefone encontrado no site: {telefone}",
        }

    return {
        "status": "sem_resultado",
        "telefone_encontrado": None,
        "todos_os_numeros": [],
        "fonte": "site_generico",
        "mensagem": "Nenhum telefone encontrado no site",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
