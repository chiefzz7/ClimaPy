# Guia de Setup no Debian 13 (Trixie) — ClimaPy

Este guia documenta a instalação, configuração local segura e execução do **ClimaPy** no **Debian GNU/Linux 13 (`trixie`)**, respeitando a **PEP 668** (sem instalar pacotes Python globalmente no sistema).

---

## 1. Requisitos do Sistema (Etapa 2 — Backend Python 3.12)

Ambiente validado na máquina:
- **Python 3.12**: `3.12.16` gerenciado via **`uv`** (instalado em `~/.local/bin/uv` com runtime isolado em `.uv-python/`)
- **Git**: `2.47+`
- **Node.js**: `20+` (usado a partir da Etapa 4 para o Frontend PWA/Capacitor)

> **Nota importante sobre `/usr/local/bin/python3.12` (3.12.0):** o binário `3.12.0` compilado localmente com GCC 14.2.0 (`--enable-optimizations`) sofre `SIGSEGV` ao compilar bytecode (`compileall` / `pip`). Por isso utilizamos o Python `3.12.16` gerenciado pelo `uv` com `--python-preference only-managed`.

> Caso precise instalar ferramentas básicas de compilação/rede no Debian 13 futuramente:
> ```bash
> sudo apt update && sudo apt install -y curl git unzip wget
> ```

---

## 2. Criando o Ambiente Virtual e Instalando o Backend

Na raiz do projeto (`/home/chiefzz/.gemini/antigravity/scratch/climapy`):

```bash
# 1. (Se ainda não tiver uv instalado) Instalar uv e baixar Python 3.12.x gerenciado
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.12

# 2. Criar ambiente virtual isolado exclusivamente com o Python 3.12 gerenciado
~/.local/bin/uv venv backend/.venv --python 3.12 --python-preference only-managed

# 3. Instalar o backend e ferramentas de dev/segurança
~/.local/bin/uv pip install --python backend/.venv/bin/python -e "backend[dev]"
```

---

## 3. Gerando Chaves Locais Seguras (Zero Chaves Externas Obrigatórias)

O **ClimaPy** não exige chaves pagas ou cadastros externos para Open-Meteo, MET Norway ou Nominatim.
As únicas chaves usadas na v1 (`DATA_ENCRYPTION_KEY` e par `VAPID_*` para Web Push) são geradas localmente e gravadas apenas no arquivo `.env` (que está no `.gitignore`):

```bash
# Copia o template caso ainda não tenha .env e grava chaves novas com permissão 0600
backend/.venv/bin/python backend/scripts/generate_keys.py --write
```

> **Atenção:** Nunca faça commit do arquivo `.env`. Em produção, ajuste `APP_ENV=production`, `ALLOWED_ORIGINS` para seu domínio HTTPS real e `VAPID_SUBJECT` para um contato válido (`mailto:...`).

---

## 4. Subindo a API Backend Localmente

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints úteis em desenvolvimento:
- Saúde da API: `http://127.0.0.1:8000/api/v1/health`
- Documentação interativa (Swagger): `http://127.0.0.1:8000/docs`
- Previsão de teste (São Paulo, 16 dias):
  `http://127.0.0.1:8000/api/v1/weather/forecast?lat=-23.55&lon=-46.63&days=16`
- Busca de cidade:
  `http://127.0.0.1:8000/api/v1/geocoding/search?q=Curitiba&lang=pt`

---

## 5. Executando Testes e Auditorias de Segurança

Dentro de `backend/`:

```bash
# Testes automatizados (100% offline com mocks HTTP)
.venv/bin/pytest -v

# Lint e formatação
.venv/bin/ruff check app tests scripts
.venv/bin/ruff format --check app tests scripts

# Verificação estrita de tipos
.venv/bin/mypy app

# Auditoria estática de segurança
.venv/bin/bandit -r app scripts
```

---

## 6. Prévia das Próximas Etapas (Android e iOS no Debian 13)

- **Etapa 4 (Web/PWA)**: usará apenas `Node.js 20+` (`npm`) já instalado.
- **Etapa 5 (Android APK local)**: exigirá `openjdk-17-jdk` + **Android SDK Command-Line Tools** (`sdkmanager` com `platform-tools`, `build-tools` e `platforms;android-34`/`35`).
- **Etapa 5 (iOS)**: compilar `.ipa` nativo requer **Xcode no macOS**. No Linux, entregaremos:
  1. **PWA instalável no iOS Safari 16.4+** com Web Push funcionando sem Xcode.
  2. Projeto Capacitor iOS + workflow pronto para **GitHub Actions (`macos-latest`)**.
