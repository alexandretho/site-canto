import os, json, random, datetime, pathlib
from textwrap import dedent
from openai import OpenAI

# Config
labels    = os.getenv("LABELS", "post, publicar")
topics    = [t.strip() for t in os.getenv("TOPIC_POOL", "").split(",") if t.strip()]
tone      = os.getenv("TONE", "Didático, encorajador, com exemplos práticos e avisos de saúde vocal")
min_words = int(os.getenv("MIN_WORDS", "280"))
max_words = int(os.getenv("MAX_WORDS", "520"))
site_name = os.getenv("SITE_NAME", "Canto Mentoria Express")

# Escolhe um tópico aleatório
topic = random.choice(topics) if topics else "Canto"

# Data em BRT (para exibir no post)
brt = datetime.datetime.utcnow() + datetime.timedelta(hours=-3)
date_pt = brt.strftime("%d/%m/%Y")

# Prompt da IA
system_prompt = f"""
Você é um assistente que escreve posts curtos em Markdown para Issues de GitHub
que serão transformadas em páginas do site {site_name}. Você deve:
- Trazer um título forte em 1 linha (começando com emoji temático).
- Introdução rápida com 1 a 2 parágrafos e uma curiosidade.
- Incluir 1 bloco de código executável ou útil (bash, yaml, exercícios descritos como passos numerados em texto, etc.) SEM QUEBRAR FENCES.
- Fechar com 3 a 5 bullets "Pontos-chave".
- Nada de links quebrados. Nada de HTML. Apenas Markdown puro.
- Tamanho alvo: entre {min_words} e {max_words} palavras.
- Tom: {tone}.
- Tópico base: {topic}.
- NÃO coloque labels ou metadados no corpo, só conteúdo do post.
- Use português do Brasil.
"""

user_prompt = f"""
Gere um post para o tema: {topic}.
Inclua a data no corpo como **Data:** {date_pt}.
O site publicará Issues com labels: {labels}, mas não escreva labels no corpo.
Retorne JSON com chaves:
"title": string (sem markdown),
"body": string (markdown completo do post).
"""

# Chama a IA (OpenAI)
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("❌ OPENAI_API_KEY não definido em secrets.")

client = OpenAI(api_key=api_key)

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role":"system","content":system_prompt},
        {"role":"user","content":user_prompt},
    ],
    temperature=0.7,
)

content = resp.choices[0].message.content.strip()

# Tenta ler como JSON; se vier texto, tenta extrair
def try_parse_json(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            return json.loads(m.group(0))
        raise

data = try_parse_json(content)

title = data.get("title", f"{topic} – Post")
body = data.get("body", f"# {title}\n\n**Data:** {date_pt}\n\n(Conteúdo)")

# Garante cabeçalho com título em markdown dentro do corpo (útil para visualização)
if not body.lstrip().startswith("# "):
    body = f"# {title}\n\n{body}"

# Caminho de saída
out_dir = pathlib.Path("out")
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "issue.md"
out_file.write_text(body, encoding="utf-8")

# Exporta outputs para o workflow
gh_out = os.getenv("GITHUB_OUTPUT")
with open(gh_out, "a", encoding="utf-8") as fh:
    fh.write(f"title={title}\n")
    fh.write(f"file={str(out_file)}\n")

print(f"✅ Gerado: {title} -> {out_file}")
