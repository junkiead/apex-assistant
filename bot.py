"""
Apex Assistant - Telegram Bot
Grupo 1 (Apex Golden Community): traduções + boas-vindas com fluxo de venda + broadcast PAMM
Grupo 2 (Apex Golden Capital - PAMM): traduções + boas-vindas simples + notícias XAUUSD via RSS
"""

import logging
import os
import feedparser
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatMemberUpdated
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatMemberHandler, filters, ContextTypes
)
from deep_translator import GoogleTranslator

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
BOT_TOKEN          = os.getenv("BOT_TOKEN")
OWNER_USERNAME     = os.getenv("OWNER_USERNAME", "apexghost_fx")
BROKER_REF_LINK    = os.getenv("BROKER_REF_LINK", "https://vigco.co/la-com-inv/mptZ3rwk")
PAMM_LINK          = os.getenv("PAMM_LINK", "https://LINK_DA_CONTA_PAMM_AQUI")
BROADCAST_INTERVAL = int(os.getenv("BROADCAST_INTERVAL", "14400"))
BOT_USERNAME       = os.getenv("BOT_USERNAME", "apexghost_fx_bot")

# IDs dos grupos
PAMM_GROUP_ID      = int(os.getenv("PAMM_GROUP_ID", "-5220645085"))  # Apex Golden Capital - PAMM

# RSS feed de Metais (Ouro/XAUUSD) da Investing.com
XAUUSD_RSS = "https://www.investing.com/rss/commodities_Metals.rss"

# Arquivo para persistir notícias já enviadas entre restarts
SENT_NEWS_FILE = "sent_news.txt"

def load_sent_news() -> set:
    if os.path.exists(SENT_NEWS_FILE):
        with open(SENT_NEWS_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_sent_news(news_id: str):
    with open(SENT_NEWS_FILE, "a") as f:
        f.write(news_id + "\n")

# Carrega notícias já enviadas do arquivo
sent_news: set = load_sent_news()

active_chats: set = set()
user_language: dict = {}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def translate_text(text: str, target: str) -> str:
    try:
        return GoogleTranslator(source="en", target=target).translate(text)
    except Exception as e:
        logger.error(f"Erro na tradução para {target}: {e}")
        return text


def get_lang(user_id: int) -> str:
    return user_language.get(user_id, "en")


def is_pamm_group(chat_id: int) -> bool:
    return chat_id == PAMM_GROUP_ID


# ─── Textos ───────────────────────────────────────────────────────────────────

WELCOME = {
    "en": (
        "🚀 *Welcome to the Apex Golden Community!*\n\n"
        "You've just entered the Apex Golden Capital paddock. Here, the gold market (XAUUSD) "
        "is handled with the precision of a Formula 1 engine. 🏎️💨\n\n"
        "Our PAMM Account is not just copy trading; it's direct access to the technology and "
        "manual execution of the enigmatic Apex Ghost.\n\n"
        "📌 *First Step: Prepare your machine*\n"
        f"Register with our official partner broker (Vantage) through the exclusive link below:\n{BROKER_REF_LINK}\n\n"
        "💼 *What happens now?*\n"
        "After registration, you can connect to the PAMM Account. Let our team and our EAs "
        "drive for you, with full transparency and optimized performance."
    ),
    "pt": (
        "🚀 *Bem-vindo à Apex Golden Community!*\n\n"
        "Você acaba de entrar no paddock da Apex Golden Capital. Aqui, o mercado de ouro (XAUUSD) "
        "é tratado com a precisão de um motor de Fórmula 1. 🏎️💨\n\n"
        "Nossa Conta PAMM não é apenas um copy trading; é o acesso direto à tecnologia e à "
        "execução manual do enigmático Apex Ghost.\n\n"
        "📌 *Primeiro Passo: Prepare sua máquina*\n"
        f"Cadastre-se na nossa corretora parceira oficial (Vantage) através do link exclusivo abaixo:\n{BROKER_REF_LINK}\n\n"
        "💼 *O que acontece agora?*\n"
        "Após o cadastro, você poderá conectar à Conta PAMM. Deixe que nossa equipe e nossos EAs "
        "pilotem por você, com total transparência e performance otimizada."
    ),
    "es": (
        "🚀 *¡Bienvenido a la Apex Golden Community!*\n\n"
        "Acabas de entrar en el paddock de Apex Golden Capital. Aquí, el mercado del oro (XAUUSD) "
        "se trata con la precisión de un motor de Fórmula 1. 🏎️💨\n\n"
        "Nuestra Cuenta PAMM no es solo copy trading; es el acceso directo a la tecnología y la "
        "ejecución manual del enigmático Apex Ghost.\n\n"
        "📌 *Primer Paso: Prepara tu máquina*\n"
        f"Regístrate en nuestro broker socio oficial (Vantage) a través del enlace exclusivo:\n{BROKER_REF_LINK}\n\n"
        "💼 *¿Qué pasa ahora?*\n"
        "Tras el registro, podrás conectarte a la Cuenta PAMM. Deja que nuestro equipo y nuestros EAs "
        "conduzcan por ti, con total transparencia y rendimiento optimizado."
    ),
}

WELCOME_PAMM_GROUP = {
    "en": (
        "🏎️ *Welcome to the Apex Golden Capital — PAMM Group!*\n\n"
        "Congratulations on your arrival and on making an excellent decision! "
        "You are now part of an exclusive community of investors who trust the precision "
        "and expertise of the Apex Ghost. 👻\n\n"
        "Stay tuned — market updates, XAUUSD news and performance reports will be shared here regularly. 📊"
    ),
    "pt": (
        "🏎️ *Bem-vindo ao Apex Golden Capital — Grupo PAMM!*\n\n"
        "Parabéns pela chegada e pela excelente decisão! "
        "Você agora faz parte de uma comunidade exclusiva de investidores que confiam na precisão "
        "e expertise do Apex Ghost. 👻\n\n"
        "Fique atento — atualizações de mercado, notícias do XAUUSD e relatórios de performance serão compartilhados aqui regularmente. 📊"
    ),
    "es": (
        "🏎️ *¡Bienvenido a Apex Golden Capital — Grupo PAMM!*\n\n"
        "¡Felicitaciones por tu llegada y por tomar una excelente decisión! "
        "Ahora formas parte de una comunidad exclusiva de inversores que confían en la precisión "
        "y experiencia del Apex Ghost. 👻\n\n"
        "Estate atento — actualizaciones del mercado, noticias de XAUUSD e informes de rendimiento se compartirán aquí regularmente. 📊"
    ),
}

PAMM_EXPLANATION = {
    "en": (
        "📊 *What is the Apex PAMM Experience?*\n\n"
        "Imagine having an elite driver managing your capital in the world's most valuable market. "
        "The PAMM Account is your access to the passenger seat in our racing team. "
        "You bring the fuel (capital) and Apex Zero takes the wheel.\n\n"
        "✅ *Our Engineering Advantages:*\n\n"
        "🏎️ *Professional Driving:* Hybrid management (EAs + Manual) focused exclusively on XAUUSD.\n\n"
        "📈 *Proportional Performance:* If our team wins, you win. Profits are distributed precisely.\n\n"
        "🔍 *Real-Time Telemetry:* Absolute transparency. Track every curve and every trade from your dashboard.\n\n"
        "⛽ *Tank Control:* The capital is yours. You maintain custody and are free to withdraw your funds according to the track rules.\n\n"
        f"👉 *Take your position on the grid:* {PAMM_LINK}"
    ),
    "pt": (
        "📊 *O que é a Experiência Apex PAMM?*\n\n"
        "Imagine ter um piloto de elite conduzindo seu capital no mercado mais valioso do mundo. "
        "A Conta PAMM é o seu acesso ao assento de passageiro na nossa escuderia. "
        "Você entra com o combustível (capital) e o Apex Zero assume o volante.\n\n"
        "✅ *Vantagens da nossa Engenharia:*\n\n"
        "🏎️ *Pilotagem Profissional:* Gestão híbrida (EAs + Manual) focada exclusivamente em XAUUSD.\n\n"
        "📈 *Performance Proporcional:* Se a nossa equipe vence, você vence. Os lucros são distribuídos de forma exata.\n\n"
        "🔍 *Telemetria em Tempo Real:* Transparência absoluta. Você acompanha cada curva e cada operação direto do seu dashboard.\n\n"
        "⛽ *Controle do Tanque:* O capital é seu. Você mantém a custódia e tem a liberdade de sacar seus fundos conforme as regras da pista.\n\n"
        f"👉 *Assuma sua posição no grid:* {PAMM_LINK}"
    ),
    "es": (
        "📊 *¿Qué es la Experiencia Apex PAMM?*\n\n"
        "Imagina tener un piloto de élite conduciendo tu capital en el mercado más valioso del mundo. "
        "La Cuenta PAMM es tu acceso al asiento de pasajero en nuestra escudería. "
        "Tú pones el combustible (capital) y Apex Zero toma el volante.\n\n"
        "✅ *Ventajas de nuestra Ingeniería:*\n\n"
        "🏎️ *Pilotaje Profesional:* Gestión híbrida (EAs + Manual) enfocada exclusivamente en XAUUSD.\n\n"
        "📈 *Rendimiento Proporcional:* Si nuestro equipo gana, tú ganas. Las ganancias se distribuyen con exactitud.\n\n"
        "🔍 *Telemetría en Tiempo Real:* Transparencia absoluta. Sigues cada curva y cada operación desde tu dashboard.\n\n"
        "⛽ *Control del Tanque:* El capital es tuyo. Mantienes la custodia y tienes libertad de retirar tus fondos según las reglas de la pista.\n\n"
        f"👉 *Toma tu posición en la parrilla:* {PAMM_LINK}"
    ),
}

NO_THANKS = {"en": "No thanks", "pt": "Não, obrigado", "es": "No, gracias"}
TALK_GHOST = {
    "en": "Talk to Apex Ghost 👻",
    "pt": "Falar direto com o Apex Ghost 👻",
    "es": "Hablar con Apex Ghost 👻"
}
GHOST_MESSAGE = {
    "en": "Hello! I'm interested in the Apex Golden Community PAMM Account.",
    "pt": "Olá! Tenho interesse na Conta PAMM da Apex Golden Community.",
    "es": "¡Hola! Estoy interesado en la Cuenta PAMM de Apex Golden Community."
}
READ_MORE = {"en": "📰 Read more", "pt": "📰 Leia mais", "es": "📰 Leer más"}


# ─── Teclados ─────────────────────────────────────────────────────────────────

def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt"),
        InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"),
    ]])


def welcome_keyboard(user_id: int):
    lang = get_lang(user_id)
    learn = {"en": "Learn more 🏎️", "pt": "Entenda mais 🏎️", "es": "Saber más 🏎️"}
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(NO_THANKS[lang], callback_data="no_thanks"),
        InlineKeyboardButton(learn[lang], callback_data="pamm_info"),
    ]])


def pamm_keyboard(user_id: int):
    lang = get_lang(user_id)
    from urllib.parse import quote
    message = quote(GHOST_MESSAGE[lang])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(NO_THANKS[lang], callback_data="no_thanks"),
        InlineKeyboardButton(TALK_GHOST[lang], url=f"https://t.me/{OWNER_USERNAME}?text={message}"),
    ]])


# ─── Notícias RSS ─────────────────────────────────────────────────────────────

async def check_news_job(ctx: ContextTypes.DEFAULT_TYPE):
    """Verifica RSS da Investing.com e envia novas notícias do XAUUSD no grupo PAMM."""
    try:
        feed = feedparser.parse(XAUUSD_RSS)
        for entry in feed.entries[:5]:  # verifica as 5 mais recentes
            news_id = entry.get("id") or entry.get("link")
            if news_id in sent_news:
                continue

            title_en = entry.get("title", "")
            link     = entry.get("link", "")

            if not title_en or not link:
                continue

            title_pt = translate_text(title_en, "pt")
            title_es = translate_text(title_en, "es")

            text = (
                "📰 *XAUUSD — Market News*\n\n"
                f"🇬🇧 {title_en}\n\n"
                f"🇧🇷 {title_pt}\n\n"
                f"🇪🇸 {title_es}"
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📰 Read / Leia / Leer", url=link)
            ]])

            await ctx.bot.send_message(
                chat_id=PAMM_GROUP_ID,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            sent_news.add(news_id)
            save_sent_news(news_id)
            logger.info(f"Notícia enviada: {title_en}")

    except Exception as e:
        logger.error(f"Erro ao buscar notícias: {e}")


# ─── Handlers ────────────────────────────────────────────────────────────────

async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = ctx.args[0] if ctx.args else ""

    if update.effective_chat.type != "private":
        active_chats.add(update.effective_chat.id)
        await update.message.reply_text("✅ Apex Assistant is active in this group!")
        return

    if args == "pamm":
        if user_id in user_language:
            await update.message.reply_text(
                text=PAMM_EXPLANATION[get_lang(user_id)],
                parse_mode="Markdown",
                reply_markup=pamm_keyboard(user_id),
            )
        else:
            await update.message.reply_text(
                "👋 *Welcome / Bem-vindo / Bienvenido!*\n\n"
                "🇬🇧 Please choose your language to continue:\n"
                "🇧🇷 Por favor, escolha seu idioma para continuar:\n"
                "🇪🇸 Por favor, elige tu idioma para continuar:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🇬🇧 English", callback_data="lang_en_pamm"),
                    InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt_pamm"),
                    InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es_pamm"),
                ]]),
            )
    else:
        await update.message.reply_text(
            "👋 *Welcome / Bem-vindo / Bienvenido!*\n\n"
            "🇬🇧 Welcome to *Apex Golden Community*! Please choose your language:\n"
            "🇧🇷 Bem-vindo à *Apex Golden Community*! Por favor, escolha seu idioma:\n"
            "🇪🇸 ¡Bienvenido a *Apex Golden Community*! Por favor, elige tu idioma:",
            parse_mode="Markdown",
            reply_markup=lang_keyboard(),
        )


async def status_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"✅ Bot online.\n📡 Active groups: {len(active_chats)}\n📰 News sent: {len(sent_news)}"
    )


async def broadcast_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Dispara o broadcast manualmente no grupo principal."""
    if update.effective_chat.type == "private":
        await update.message.reply_text("⚠️ This command must be used inside the group.")
        return
    if is_pamm_group(update.effective_chat.id):
        await update.message.reply_text("⚠️ This command is not available in this group.")
        return
    active_chats.add(update.effective_chat.id)
    await broadcast_job(ctx)


async def news_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Força verificação de notícias manualmente (para testes)."""
    if update.effective_chat.id != PAMM_GROUP_ID:
        await update.message.reply_text("⚠️ This command is only available in the PAMM group.")
        return
    await update.message.reply_text("🔍 Checking for news...")
    await check_news_job(ctx)


async def translate_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Traduz mensagens em inglês do grupo para PT e ES."""
    msg = update.message
    if not msg or not msg.text:
        return
    if msg.from_user.is_bot:
        return

    active_chats.add(msg.chat_id)
    text = msg.text.strip()
    if not text:
        return

    pt = translate_text(text, "pt")
    es = translate_text(text, "es")

    await msg.reply_text(
        f"🇧🇷 *PT:* {pt}\n\n🇪🇸 *ES:* {es}",
        parse_mode="Markdown"
    )


async def new_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Boas-vindas diferentes dependendo do grupo."""
    result: ChatMemberUpdated = update.chat_member
    if result.new_chat_member.status not in ("member", "restricted"):
        return
    user = result.new_chat_member.user
    if user.is_bot:
        return

    chat_id = result.chat.id

    # ── Grupo PAMM: boas-vindas simples no grupo, sem venda ──
    if is_pamm_group(chat_id):
        await ctx.bot.send_message(
            chat_id=chat_id,
            text=(
                f"👋 [{user.first_name}](tg://user?id={user.id})\n\n"
                f"{WELCOME_PAMM_GROUP['en']}\n\n"
                "─────────────────────\n\n"
                f"{WELCOME_PAMM_GROUP['pt']}\n\n"
                "─────────────────────\n\n"
                f"{WELCOME_PAMM_GROUP['es']}"
            ),
            parse_mode="Markdown",
        )

    # ── Grupo principal: botão para continuar no privado com o bot ──
    else:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "👋 Start / Começar / Comenzar",
                url=f"https://t.me/{BOT_USERNAME}?start=welcome"
            )
        ]])
        await ctx.bot.send_message(
            chat_id=chat_id,
            text=(
                f"👋 *Welcome / Bem-vindo / Bienvenido*, [{user.first_name}](tg://user?id={user.id})!\n\n"
                "🇬🇧 Welcome to *Apex Golden Community*! Click below to get started in private.\n"
                "🇧🇷 Bem-vindo à *Apex Golden Community*! Clique abaixo para continuar no privado.\n"
                "🇪🇸 ¡Bienvenido a *Apex Golden Community*! Haz clic abajo para continuar en privado."
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("lang_") and not data.endswith("_pamm"):
        lang = data.split("_")[1]
        user_language[user_id] = lang
        await query.edit_message_text(
            text=WELCOME[lang],
            parse_mode="Markdown",
            reply_markup=welcome_keyboard(user_id),
        )

    elif data.endswith("_pamm"):
        lang = data.split("_")[1]
        user_language[user_id] = lang
        await query.edit_message_text(
            text=PAMM_EXPLANATION[lang],
            parse_mode="Markdown",
            reply_markup=pamm_keyboard(user_id),
        )

    elif data == "pamm_info":
        lang = get_lang(user_id)
        await query.edit_message_text(
            text=PAMM_EXPLANATION[lang],
            parse_mode="Markdown",
            reply_markup=pamm_keyboard(user_id),
        )

    elif data == "no_thanks":
        lang = get_lang(user_id)
        msgs = {
            "en": "👍 No problem! Feel free to reach out anytime.",
            "pt": "👍 Sem problemas! Estamos à disposição.",
            "es": "👍 ¡Sin problema! Estamos disponibles cuando quieras.",
        }
        await query.edit_message_text(msgs[lang])


async def broadcast_job(ctx: ContextTypes.DEFAULT_TYPE):
    """Broadcast a cada 4h apenas nos grupos principais (não no grupo PAMM)."""
    text = (
        "📈 *Apex Golden Community — Trading Opportunity*\n\n"
        "🇬🇧 Join our broker and start copy trading with our PAMM account!\n"
        "🇧🇷 Entre na corretora e comece o copy trading com nossa conta PAMM!\n"
        "🇪🇸 ¡Únete al bróker y empieza el copy trading con nuestra cuenta PAMM!\n\n"
        f"👉 {BROKER_REF_LINK}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📊 Learn more / Saiba mais / Saber más",
            url=f"https://t.me/{BOT_USERNAME}?start=pamm"
        )
    ]])

    for chat_id in list(active_chats):
        if is_pamm_group(chat_id):
            continue  # nunca envia broadcast no grupo PAMM
        try:
            await ctx.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning(f"Erro ao enviar broadcast para {chat_id}: {e}")
            active_chats.discard(chat_id)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        translate_message
    ))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Broadcast a cada 4h (apenas grupo principal)
    app.job_queue.run_repeating(broadcast_job, interval=BROADCAST_INTERVAL, first=BROADCAST_INTERVAL)

    # Verifica notícias a cada 15 minutos
    app.job_queue.run_repeating(check_news_job, interval=900, first=30)

    logger.info("🤖 Apex Assistant iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()