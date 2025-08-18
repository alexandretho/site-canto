#!/usr/bin/env python3
import os, json, random, datetime, pathlib, re
from textwrap import dedent
from slugify import slugify

# ===== Config por ENV =====
topics     = [t.strip() for t in os.getenv("TOPIC_POOL", "").split(",") if t.strip()]
tone       = os.getenv("TONE", "Didático, encorajador, com exemplos práticos e avisos de saúde vocal")
min_words  = int(os.getenv("MIN_WORDS", "280"))
max_words  = int(os.getenv("MAX_WORDS", "520"))
site_name  = os.getenv("SITE_NAME", "Canto & Mentoria")
site_url   = os.getenv("SITE_URL", "https://example.com")
model_id   = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-lite-preview-02-05:free")
api_key    = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise SystemExit("❌ Faltando OPENROUTER_API_KEY (adicione em Secrets).")

topic = random.choice(topics) if topics else "Curiosidades sobre a voz"

# Data local (America/Sao_Paulo)
try:
    from zoneinfo import ZoneInfo
    now_sp = datetime.datetime.now(ZoneInfo("America/Sao_Paulo"))
except Exception:
    now_sp = datetime.datetime.utcnow() - datetime.timedelta(hours=3)

date_pt   = now_sp.strftime("%d/%m/%Y")
date_iso  = now_sp.strftime("%Y-%m-%d")
stamp     = now_sp.strftime("%Y-%m-%d-%H%M")

# ===== Prompts =====
system_prompt = f"""
Você é um redator especialista em canto e fonoaudiologia.
Escreva em PT-BR, tom {tone}, para cantores iniciantes e intermediários.

Regras:
- Markdown puro (sem HTML).
- Estrutura:
  # Título (comece com um emoji temático: 🎤, 🗣️, 🎶)
  Introdução (1–2 parágrafos) com gancho/curiosidade.
  ## Conceitos essenciais
  ## Exercícios práticos (bullets ou passos)
  ## Erros comuns e como evitar
  ## Quando procurar um fono/mentor
  ### Pontos-chave (3–5 bullets)
- Inclua a linha: **Data:** {date_pt}
- Tamanho entre {min_words} e {max_words} palavras.
"""

user_prompt = f"""
Gere um post sobre: {topic}.
Retorne JSON com chaves:
"title": string (sem markdown),
"body": string (markdown completo do post).
"""

# ===== Chamada OpenRouter usando OpenAI client (com base_url) =====
from openai import OpenAI
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

extra_headers = {
    "HTTP-Referer": site_url,                   # ASCII
    "X-Title": f"{site_name} - AI Post Files",  # ASCII
}

resp = client.chat.completions.create(
    model=model_id,
    messages=[
        {"role":"system","content":system_prompt.strip()},
        {"role":"user","content":user_prompt.strip()},
    ],
    temperature=0.7,
    max_tokens=900,
    extra_headers=extra_headers,
)
content = resp.choices[0].message.content.strip()

# ===== Parse robusto de JSON da resposta =====
def try_parse_json(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            return json.loads(m.group(0))
        raise

data = try_parse_json(content)
title = data.get("title", f"{topic}").strip()
body  = data.get("body", f"# {title}\n\n**Data:** {date_pt}\n\n(Conteúdo)").strip()

# Garante H1
if not body.lstrip().startswith("# "):
    body = f"# {title}\n\n{body}"

# ===== Salva arquivo Markdown completo em posts/ =====
posts_dir = pathlib.Path("posts")
posts_dir.mkdir(parents=True, exist_ok=True)
fname = f"{stamp}-{slugify(title)}.md"
md_path = posts_dir / fname
md_path.write_text(body, encoding="utf-8")

# ===== Atualiza posts.json para o index.html (formato {"posts":[...]}) =====
json_path = pathlib.Path("posts.json")
if json_path.exists():
    try:
        root = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        root = {"posts": []}
else:
    root = {"posts": []}

# Gera um pequeno resumo/trecho em texto plano (sem markdown pesado)
def md_to_excerpt(md: str, max_len=500) -> str:
    # remove code fences
    md = re.sub(r"```[\\s\\S]*?```", "", md)
    # remove # títulos
    md = re.sub(r"^#+\\s*", "", md, flags=re.MULTILINE)
    # remove links [txt](url) -> txt
    md = re.sub(r"\\[([^\\]]+)\\]\\([^\\)]+\\)", r"\\1", md)
    # remove ênfases * _ > -
    md = re.sub(r"[>*_`-]", " ", md)
    # pega primeiras linhas após H1
    lines = [ln.strip() for ln in md.splitlines() if ln.strip()]
    if lines and lines[0].startswith("Data:"):
        lines = lines[1:]
    excerpt = " ".join(lines)[:max_len].strip()
    return excerpt

root["posts"].append({
    "title": title,
    "date": date_iso,
    "content": md_to_excerpt(body),
    # opcional: se quiser usar depois para linkar o post completo
    "file": f"./posts/{fname}"
})

# Ordena por data desc e limita a 100
root["posts"].sort(key=lambda x: x.get("date",""), reverse=True)
root["posts"] = root["posts"][:100]

json_path.write_text(json.dumps(root, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"✅ Gerado Markdown: {md_path}")
print(f"🗂️  Atualizado: {json_path}")
