# ClimaPy

Aplicativo multiplataforma de previsão do tempo (**Web / PWA**, **Android** e **iOS**) com backend **Python 3.12 (FastAPI)**, focado em **previsão horária detalhada para 3 dias (72 horas)** e **visão estendida de até 16 dias**, **lembretes personalizáveis sem login** e **arquitetura preparada para IA climática**.

---

## Principais Recursos

- **Previsão Horária Completa (72h em destaque + até 16 dias)**:
  - Temperatura e sensação térmica (`°C`), ponto de orvalho (`°C`), umidade relativa (`%`)
  - Probabilidade de chuva (`%`), volume (`mm`), garoa/pancadas e horas de precipitação
  - Velocidade, rajadas (`km/h`) e **direção do vento** com rosa dos ventos em português (`N`, `ENE`, `L`, `SO`...)
  - Pressão atmosférica ao nível do mar e em superfície (`hPa`), cobertura de nuvens (`%`), visibilidade (`km`), índice UV, nascer/pôr do sol e duração de luz/sol
  - Qualidade do ar complementar (`european_aqi`, `us_aqi`, `pm2_5`, `pm10`, `CO`, `NO2`, `SO2`, `O3`, poeira)
  - Modo de payload compacto (`include_full_hourly=false`) para economizar dados móveis mantendo 72h horárias + 16 dias diários
- **APIs Gratuitas com Fallback Automático & Zero Chaves Obrigatórias na v1**:
  - **Primária**: Open-Meteo (previsão 16 dias, qualidade do ar e busca de cidades em português)
  - **Fallback**: MET Norway / Yr.no (`api.met.no`)
  - **Geocodificação reversa opcional**: OpenStreetMap Nominatim
- **Privacidade & Segurança por Design**:
  - **Zero contas, zero login, zero PII** — favoritos e preferências ficam apenas no dispositivo
  - **Zero SQL Injection** (SQLAlchemy 2.0 ORM/Core parametrizado)
  - **Zero segredos no código** (`.env` local ignorado no Git; geração local de chaves Fernet e VAPID P-256)
  - **Anti-SSRF** (allowlist fixa HTTPS para provedores e `follow_redirects=False`)
  - **Anti-IDOR sem login** (capability token `X-Reminder-Token` comparado via `hmac.compare_digest` contra hash SHA-256)
  - **Headers HTTP endurecidos** (CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`) e rate limiting (`slowapi`)

---

## Stack Aprovada (ADR-001)

- **Backend & Futura IA**: Python 3.12, FastAPI, Pydantic v2, httpx (async), SQLAlchemy 2.0, cachetools, slowapi, cryptography (Fernet).
- **Frontend Multiplataforma (Etapas 4–5)**: Vite + TypeScript + React + Tailwind CSS (PWA com Web Push VAPID) + Capacitor para empacotamento Android/iOS com notificações locais.

---

## Início Rápido (Debian 13 / Linux)

Consulte também [docs/DEBIAN_SETUP.md](./docs/DEBIAN_SETUP.md).

```bash
# 1. Instalar uv e Python 3.12 gerenciado (evita incompatibilidades de builds antigos)
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.12

# 2. Criar virtualenv isolado e instalar backend + ferramentas dev
~/.local/bin/uv venv backend/.venv --python 3.12 --python-preference only-managed
~/.local/bin/uv pip install --python backend/.venv/bin/python -e "backend[dev]"

# 3. Gerar chaves locais (Fernet + VAPID) em .env (permissão 0600, ignorado no Git)
backend/.venv/bin/python backend/scripts/generate_keys.py --write

# 4. Subir a API FastAPI (Terminal 1)
cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 5. Subir o Frontend Web/PWA (Terminal 2)
cd frontend && npm install && npm run dev
```

Documentação interativa local da API: `http://127.0.0.1:8000/docs`  
Aplicativo Web/PWA local: `http://127.0.0.1:5173`

### Testes e Auditorias (100% Offline)

```bash
# Backend
cd backend
.venv/bin/pytest -v
.venv/bin/ruff check app tests scripts && .venv/bin/ruff format --check app tests scripts
.venv/bin/mypy app
.venv/bin/bandit -r app scripts

# Frontend
cd ../frontend
npm run typecheck
npm test
npm run build
```

---

## Documentação e Roadmap

- Arquitetura, pesquisa de APIs e segurança: [CONTEXT.md](./CONTEXT.md)
- Regras operacionais de desenvolvimento: [AGENTS.md](./AGENTS.md)
- Setup detalhado no Debian 13: [docs/DEBIAN_SETUP.md](./docs/DEBIAN_SETUP.md)

### Etapas do Projeto
1. **Etapa 1** — Pesquisa de APIs gratuitas, arquitetura e documentos base (`CONTEXT.md`, `AGENTS.md`) ✅
2. **Etapa 2 + 2.5** — Backend Python 3.12 seguro, provedores Open-Meteo/MET Norway/Nominatim, cache TTL, rosa dos ventos, pressão/orvalho/visibilidade, modo compacto e testes ✅
3. **Etapa 3** — Lembretes sem login e motor de notificações Web Push (VAPID + `APScheduler` + capability token + Fernet + anti-SSRF) ✅
4. **Etapa 4** — Frontend Web/PWA mobile-first (3 dias + até 16 dias + gráficos horários + favoritos locais + SW Web Push) ✅
5. **Etapa 5** — Empacotamento Android (APK) e preparo iOS (Capacitor + GitHub Actions `macos-latest`)
6. **Etapa 6** — Camada de IA climática em Python (`backend/app/services/ai/`)

---

## Atribuição de Dados

Dados meteorológicos e geográficos fornecidos gratuitamente por:
- [Open-Meteo](https://open-meteo.com/) (CC BY 4.0 — uso não comercial no tier gratuito)
- [MET Norway](https://api.met.no/) (CC BY 4.0)
- [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org/) (ODbL)
