# CONTEXT.md — ClimaPy

> Documento de contexto arquitetural, pesquisa de APIs, modelo de segurança e roadmap do projeto **ClimaPy**.
> Leia este arquivo integralmente antes de iniciar qualquer nova etapa ou alteração no repositório.

---

## 1. Visão Geral do Projeto (`ClimaPy`)

O **ClimaPy** é um aplicativo de previsão do tempo multiplataforma (**Web / PWA**, **Android** e **iOS**) com backend em **Python**, projetado desde o início com foco em:

- **Previsão horária de alta clareza**: foco principal na janela de **3 dias (72 horas)** em destaque, com expansão contínua para o máximo suportado gratuitamente — **até 16 dias** (diária + horária).
- **Zero contas, zero login, zero PII**: o aplicativo não possui cadastro de usuários, senhas, e-mails ou cookies de rastreamento, evitando armazenar dados pessoais (aderente à LGPD por design).
- **Lembretes e notificações personalizáveis**: o usuário escolhe os horários e dias (pontuais ou recorrentes na semana) em que deseja receber alertas climáticos, além da janela desejada (hoje, amanhã ou próximos 3 dias) e filtros condicionais opcionais (ex.: notificar apenas se probabilidade de chuva ≥ X%).
- **Segurança por padrão (Security by Design)**: zero SQL Injection, zero segredos ou chaves no código-fonte, proteção contra IDOR sem login, proteção anti-SSRF, validação rigorosa de entrada e headers HTTP endurecidos.
- **Pronto para IA em Python**: arquitetura modular preparada para acoplar, em etapa futura, análises climáticas profundas, detecção de anomalias/mudanças bruscas e recomendações contextuais (vestuário, atividades externas, alertas preventivos) via modelos locais ou APIs LLM.

---

## 2. Funcionalidades Planejadas

### 2.1 Dados Meteorológicos e Visões
- **Visão Principal (Destaque — 3 dias / 72 horas)**:
  - Condição atual resumida (temperatura, sensação térmica, ponto de orvalho, pressão atmosférica, visibilidade, ícone/descrição WMO em PT-BR, umidade, vento com direção cardinal).
  - Linha do tempo e gráfico hora a hora para as próximas **72 horas**:
    - Temperatura (`temperature_2m`, °C), sensação térmica (`apparent_temperature`, °C) e ponto de orvalho (`dew_point_2m`, °C)
    - Umidade relativa do ar (`relative_humidity_2m`, %)
    - Pressão atmosférica ao nível do mar (`pressure_msl`, hPa) e em superfície (`surface_pressure`, hPa)
    - Visibilidade (`visibility`, km)
    - Probabilidade de precipitação (`precipitation_probability`, %) e volume/quantidade de chuva (`precipitation`, `rain`, `showers`, mm)
    - Velocidade, rajadas (`wind_speed_10m`, `wind_gusts_10m`, km/h) e direção do vento (`wind_direction_10m` + rosa dos ventos PT-BR)
    - Índice UV (`uv_index`) e cobertura de nuvens (`cloud_cover`, %)
    - Nascer e pôr do sol (`sunrise`, `sunset`)
- **Visão Estendida (Até 16 dias)**:
  - Resumo diário (mínima, máxima, chance/acumulado/horas de chuva, vento máximo, direção dominante, UV máximo, duração de luz/sol, código WMO) para até **16 dias**.
  - Expansão hora a hora de qualquer um dos 16 dias suportados pelo provedor primário (com suporte ao parâmetro `include_full_hourly=false` para payload leve no mobile).
- **Qualidade do Ar (Complementar & Insumo para IA)**:
  - `pm2_5`, `pm10`, monóxido de carbono (`carbon_monoxide`), dióxido de nitrogênio (`nitrogen_dioxide`), dióxido de enxofre (`sulphur_dioxide`), ozônio (`ozone`), poeira (`dust`), `european_aqi` e `us_aqi` via Open-Meteo Air Quality API.

### 2.2 Localização e Favoritos (Sem Conta)
- Busca de cidades em português (`language=pt`) via Geocoding.
- Detecção opcional por GPS do navegador/dispositivo (mediante permissão explícita), usando Reverse Geocoding apenas para exibir o nome da localidade.
- Lista de cidades favoritas e preferências (unidade °C/°F, tema claro/escuro) armazenadas **exclusivamente no dispositivo** (`localStorage` / `IndexedDB` / armazenamento nativo do Capacitor).

### 2.3 Lembretes e Notificações Personalizadas
O usuário pode criar regras como *"Todos os dias às 07:00 me avise o clima de hoje"*, *"Seg/Qua/Sex às 18:30 avise se a chance de chuva para amanhã for ≥ 60%"* ou *"Lembrete pontual no sábado às 08:00 para os próximos 3 dias"*.

A entrega é desenhada de acordo com a plataforma, mantendo privacidade máxima:

1. **Android e iOS (App Nativo via Capacitor)**:
   - **Notificações Locais Agendadas** (`@capacitor/local-notifications`).
   - Alimentadas pela previsão em cache (até 16 dias) e atualizadas quando o app abre ou sincroniza em segundo plano.
   - Respeitam automaticamente o limite rígido do iOS de **64 notificações locais pendentes** através de uma **fila em janela deslizante** (cancela passadas e agenda sempre os próximos disparos dentro do limite).
   - No Android 13+ / 14+, solicita `POST_NOTIFICATIONS` em tempo de execução e trata agendamentos com segurança (sem depender de `USE_EXACT_ALARM` restritivo na Play Store).
   - Funciona mesmo offline para lembretes já agendados e mantém **zero dados no servidor**.

2. **Web / PWA (Navegadores Desktop/Mobile e iOS 16.4+ instalado na Tela de Início)**:
   - **Web Push anônimo padrão W3C + VAPID** (`pywebpush` + `APScheduler` no backend Python).
   - Sem login e sem PII: o backend armazena apenas:
     - `id`: UUIDv4 aleatório gerado pelo servidor
     - `subscription_encrypted`: payload `PushSubscription` criptografado em repouso (Fernet/AES)
     - `location_name` + `lat_rounded` / `lon_rounded`: coordenadas arredondadas para **2 casas decimais (~1,1 km)** — precisão meteorológica sem rastrear endereço residencial exato
     - `timezone`: fuso IANA validado via `zoneinfo.available_timezones()` (ex.: `America/Sao_Paulo`)
     - `schedule_rule`: horário, dias da semana / data pontual, janela (hoje/amanhã/3 dias) e limiar opcional de chuva (%)
     - `token_hash`: hash SHA-256 de um **capability token** aleatório enviado uma única vez ao dispositivo

---

## 3. Pesquisa e Estratégia de APIs Gratuitas (Provider Pattern)

Para garantir máxima disponibilidade, cobertura de até **16 dias hora a hora** e **zero chaves obrigatórias** na v1, o backend adota o **Provider Pattern** com fallback automático e cache inteligente.

### 3.1 Tabela Comparativa das APIs Pesquisadas

| Provedor | Horizonte Horário | Chave de API | Limite Gratuito | Uso Comercial (Free) | Dados Chave | Papel no ClimaPy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Open-Meteo** (`api.open-meteo.com`) | **Até 16 dias** (`forecast_days=16`) | **Não** | 10.000 req/dia, 5.000/h, 600/min | Não (CC BY 4.0 não comercial) | Temp, sensação, umidade, `precipitation_probability`, chuva (mm), vento, rajadas, UV, nuvens, WMO + Geocoding PT + Air Quality | **Primária (Padrão)** |
| **MET Norway / Yr.no** (`api.met.no`) | Até ~9 dias (horário ~60h + blocos 6h) | **Não** (exige `User-Agent` único) | Uso justo sem abuso (cache obrigatório) | **Sim** (CC BY 4.0) | Temp, umidade, vento, precipitação, símbolos; modelos globais/ECMWF | **Fallback automático** |
| **WeatherAPI.com** | **3 dias** no plano Free | **Sim** (gratuita, sem cartão) | 100.000 req/mês | **Sim** | Horário 3 dias, chance de chuva, umidade, UV, AQI | **Opcional** (se houver chave comercial no `.env`) |
| **OpenWeatherMap** | 48h (One Call 3.0) / blocos 3h (v2.5) | **Sim** (One Call 3.0 exige cartão) | 1.000 req/dia (One Call 3.0) | Restrito por plano | `pop`, temp, chuva | **Descartada** como primária |
| **Nominatim / OSM** (`nominatim.openstreetmap.org`) | N/A (Reverse Geocoding) | **Não** (exige `User-Agent`) | Máx. 1 req/s (cache obrigatório) | Sim (ODbL com atribuição) | Nome da cidade/estado por lat/lon | **Opcional** (apenas ao usar GPS) |

### 3.2 Estratégia de Cache e Resiliência
- **Normalização de Coordenadas**: arredondamento para **2 casas decimais** (`~1,1 km`) antes da chave de cache e das chamadas externas, aumentando a taxa de acerto do cache e preservando a privacidade do usuário.
- **TTL de Cache**:
  - Previsão do tempo e Qualidade do ar: **15 a 30 minutos**.
  - Geocoding (busca por nome) e Reverse Geocoding (GPS): **24 horas**.
- **Fallback Transparente**: se Open-Meteo retornar timeout, erro 5xx ou 429, o `WeatherService` recorre automaticamente ao `MetNorwayProvider` (ou `WeatherAPIProvider`, caso `WEATHERAPI_KEY` esteja configurada) e retorna um contrato unificado indicando a fonte e atribuição.
- **Atribuição Legal na UI**: exibir rodapé discreto creditando *Open-Meteo*, *MET Norway* e *OpenStreetMap* conforme licenças CC BY 4.0 / ODbL.

---

## 4. Decisão de Arquitetura (ADR-001) — Stack Proposta vs. Alternativa

> **Status:** `ACEITA — Opção A (Backend Python 3.12 + FastAPI + Frontend Vite/TypeScript/React PWA + Capacitor).`

### 4.1 Opção A — Python-First Híbrida (Adotada)
- **Backend + Motor de Notificações + Futura IA**:
  - **Python 3.12 (`3.12.16` gerenciado via `uv`)** + **FastAPI** + **Pydantic v2** + **httpx** (async) + **SQLAlchemy 2.0 (async)** + **SQLite** (ou PostgreSQL em produção futura) + **APScheduler** + **pywebpush** + **cryptography (Fernet)**.
- **Frontend Multiplataforma**:
  - **Vite + TypeScript + React + Tailwind CSS** compilado como:
    1. **Web / PWA** (Service Worker para offline + Web Push no navegador e no iOS 16.4+ na Tela de Início).
    2. **Android (`.apk` / `.aab`)** e **iOS (`.ipa`)** via **Capacitor** com `@capacitor/local-notifications` e `@capacitor/geolocation`.
- **Por que é a recomendada**:
  - Mantém toda a regra de negócio, agregação meteorológica, segurança, scheduler e a futura camada de **IA 100% em Python**.
  - Gera **PWA imediato** no Debian 13 (funciona no navegador e no iOS sem precisar de Mac desde o primeiro dia).
  - Gera **APK Android leve** e com suporte maduro a notificações locais agendadas offline.
  - Experiência visual fluida de app de clima (gráficos horários responsivos, gestos, animações suaves).

### 4.2 Opção B — 100% Python (FastAPI + Flet / Flutter)
- **Alternativa caso o usuário deseje evitar TypeScript/React na camada visual**.
- Usa **Flet** (Python sobre Flutter) para gerar Web, Android e iOS consumindo o mesmo backend FastAPI em Python.
- **Trade-offs registrados com transparência**:
  - O APK Android gerado costuma ser bem maior (~35 a 60 MB), pois empacota o runtime Python + bibliotecas + engine Flutter.
  - Execução de tarefas em background no mobile em Flet sofre limitações severas de sandboxing do sistema operacional (Doze mode / iOS background limits).
  - Suporte a Web Push (W3C Service Worker) no Flutter Web/Flet exige pontes JS extras e costuma ser menos direto que em um PWA nativo.

---

## 5. Pilares de Segurança e Privacidade (Invioláveis)

1. **Zero SQL Injection**:
   - Acesso ao banco **100% via SQLAlchemy 2.0 ORM / Core com bind parameters**.
   - Proibido concatenar variáveis ou usar f-strings em consultas SQL (`text()` apenas sem interpolação, se estritamente inevitável).
2. **Zero Segredos no Código**:
   - Nenhuma chave VAPID, chave Fernet, token de API opcional ou senha hardcoded.
   - Carregamento exclusivo via variáveis de ambiente (`pydantic-settings`) e `.env` local (listado no `.gitignore`).
   - Repositório inclui apenas `.env.example` com valores de exemplo vazios/placeholders.
3. **Zero IDOR sem Sistema de Contas**:
   - Ao criar um lembrete Web Push, o backend gera um **capability token** aleatório (`secrets.token_urlsafe(32)`), armazena apenas seu **hash SHA-256** no banco e devolve o token em texto claro **uma única vez** na resposta da criação.
   - Operações de leitura individual, pausa, atualização ou exclusão exigem o header `X-Reminder-Token`, validado em tempo constante via `hmac.compare_digest`.
4. **Criptografia de Dados de Push em Repouso**:
   - O objeto `PushSubscription` (`endpoint`, `p256dh`, `auth`) contém chaves criptográficas do navegador do usuário e é armazenado **cifrado com Fernet (AES-128-CBC + HMAC-SHA256)** usando `DATA_ENCRYPTION_KEY` do `.env`.
5. **Proteção Anti-SSRF**:
   - Chamadas meteorológicas só podem atingir **allowlist fixa** de domínios HTTPS (`api.open-meteo.com`, `geocoding-api.open-meteo.com`, `air-quality-api.open-meteo.com`, `api.met.no`, `api.weatherapi.com`, `nominatim.openstreetmap.org`).
   - Endpoints de `PushSubscription` passam por validação rigorosa: protocolo `https://`, portas padrão, **allowlist de domínios de push** conhecidos (FCM/Google, Mozilla, Apple/Safari, Windows WNS, Edge) ou bloqueio explícito via resolução DNS de IPs privados, loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`), multicast e redes reservadas, além de `follow_redirects=False`.
6. **Validação Estrita & Rate Limiting**:
   - Pydantic v2 validando latitude (`-90` a `90`), longitude (`-180` a `180`), `forecast_days` (`1` a `16`), nomes de cidade (tamanho máximo e caracteres permitidos), fusos IANA (`zoneinfo.available_timezones()`) e limiares numéricos.
   - Rate limiting por IP (`slowapi`) especialmente nas rotas de criação de lembretes, teste de push e busca geocoding.
7. **Hardening Web & Sanitização de Logs**:
   - Headers HTTP de segurança via middleware: `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, `Strict-Transport-Security` (em HTTPS).
   - CORS com origens explicitamente configuradas via `.env`.
   - Prevenção de XSS no frontend (proibição de `dangerouslySetInnerHTML` / `innerHTML`).
   - Logs estruturados sem registro de `PushSubscription`, capability tokens ou coordenadas precisas.

---

## 6. Ambiente Debian 13 (Trixie), Chaves e Dependências

### 6.1 Estado Atual Detectado na Máquina
- **Sistema Operacional**: Debian GNU/Linux 13 (`trixie`)
- **Python do Projeto**: `3.12.16` gerenciado via `uv 0.13.9` (runtime isolado em `.uv-python/`, referenciado por `backend/.venv`); evita `/usr/local/bin/python3.12` (`3.12.0` compilado com GCC 14.2.0 + `--enable-optimizations`) por apresentar `SIGSEGV` ao compilar bytecode
- **Node.js**: `v20.19.2`
- **Git**: `2.47.3`

### 6.2 Guia de Chaves e Serviços Externos
- **Obrigatórias para a v1**: **NENHUMA chave externa ou conta de API é necessária.**
  - Open-Meteo e MET Norway não exigem API Key.
  - Chaves **VAPID** (Web Push) e **Fernet** (`DATA_ENCRYPTION_KEY`) são geradas **100% localmente** via script utilitário seguro no próprio projeto e salvas apenas no `.env`.
- **Variáveis Locais de Configuração (`.env`)**:
  - `APP_ENV`, `APP_USER_AGENT` (identificação obrigatória para MET Norway e Nominatim), `ALLOWED_ORIGINS`
  - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (ex.: `mailto:contato@seudominio.com` ou URL local em dev)
  - `DATA_ENCRYPTION_KEY` (chave Fernet 32-byte base64 gerada localmente)
- **Opcionais Futuras**:
  - `WEATHERAPI_KEY` (caso deseje ativar WeatherAPI.com como provedor comercial adicional)
  - `AI_PROVIDER`, `GEMINI_API_KEY` / `OPENAI_API_KEY` / `OLLAMA_BASE_URL` (Etapa 6 — camada de IA)

### 6.3 Dependências por Etapa no Debian 13
- **Etapa 2 (Backend Python)**:
  - `uv` + Python `3.12.16` (`--python-preference only-managed`) criando o ambiente virtual isolado `backend/.venv` (respeitando PEP 668 do Debian 13 e evitando o binário `3.12.0` local).
- **Etapa 3 e 4 (Frontend Web/PWA + Notificações)**:
  - `Node.js 20+` (já instalado) + `npm`.
- **Etapa 5 (Empacotamento Mobile Android e iOS)**:
  - **Android (Local no Debian 13)**: `openjdk-17-jdk`, `unzip`, `wget` + Android SDK Command-Line Tools (`platforms;android-35` ou `34`, `build-tools`, `platform-tools`).
  - **iOS (Limitação de Plataforma da Apple)**: compilar um `.ipa` nativo exige **Xcode em macOS**. No Debian 13 entregaremos:
    1. **PWA instalável no iOS Safari (16.4+)** com notificações Web Push funcionando imediatamente sem Xcode.
    2. Projeto Capacitor iOS + workflow pronto do **GitHub Actions (`macos-latest`)** para gerar o build iOS na nuvem quando desejar publicar na App Store / TestFlight.

---

## 7. Estrutura de Diretórios Planejada

```text
climapy/
├── CONTEXT.md                  # Contexto arquitetural, APIs, segurança e roadmap
├── AGENTS.md                   # Regras invioláveis e padrões para agentes/devs
├── .gitignore                  # Ignora .env, .venv, node_modules, builds, keystores, *.db
├── .env.example                # Modelo seguro de variáveis de ambiente (sem segredos)
├── backend/
│   ├── pyproject.toml          # Dependências e configs (ruff, mypy, pytest, bandit)
│   ├── scripts/
│   │   └── generate_keys.py    # Gera chaves VAPID + Fernet localmente
│   ├── app/
│   │   ├── main.py             # Entrypoint FastAPI, lifespan, middlewares, rotas
│   │   ├── core/
│   │   │   ├── config.py       # Settings com pydantic-settings
│   │   │   ├── security.py     # Criptografia Fernet, hashes SHA-256, anti-SSRF, headers
│   │   │   └── rate_limit.py   # Configuração slowapi
│   │   ├── db/
│   │   │   ├── base.py         # Engine async SQLAlchemy + sessão
│   │   │   └── models.py       # Modelos ORM (Reminder, Cache persistente se aplicável)
│   │   ├── schemas/            # Contratos Pydantic v2 (Weather, Geocoding, Reminder, AI)
│   │   ├── providers/          # Provider Pattern (base, open_meteo, met_norway, weatherapi, nominatim)
│   │   ├── services/
│   │   │   ├── weather_service.py
│   │   │   ├── cache_service.py
│   │   │   ├── push_service.py
│   │   │   ├── scheduler_service.py
│   │   │   └── ai/             # Interface abstrata e stub pronto para Etapa 6 (IA)
│   │   └── api/v1/             # Endpoints REST versionados
│   └── tests/                  # Testes pytest com mocks HTTP (sem rede)
├── frontend/
│   ├── package.json
│   ├── capacitor.config.ts
│   ├── public/                 # Manifest PWA e ícones
│   └── src/
│       ├── services/           # Cliente HTTP, notificações locais vs Web Push, storage local
│       ├── components/         # Visão 3 dias, 16 dias, gráficos horários, lembretes
│       └── ...
├── docs/
│   └── DEBIAN_SETUP.md         # Guia detalhado de instalação e build no Debian 13
└── .github/
    └── workflows/              # CI de testes/segurança + build opcional iOS macos-latest
```

---

## 8. Roadmap em 6 Etapas

1. **Etapa 1 (Concluída) — Pesquisa, Contextualização e Documentação Base**: pesquisa de APIs gratuitas, definição arquitetural e criação de `CONTEXT.md` e `AGENTS.md`.
2. **Etapa 2 + 2.5 (Concluída) — Fundação Segura, Backend Python 3.12 & Refinamento de Dados**: estrutura do repositório, `README.md`, `.gitignore`, `.env.example`, gerador local de chaves, API FastAPI, `OpenMeteoProvider` (16 dias horários completos com direção do vento em PT-BR, pressão atmosférica, ponto de orvalho, visibilidade, duração de sol/luz + Geocoding + Air Quality ampliada), `MetNorwayProvider` (fallback com média vetorial do vento), `NominatimReverseGeocodingProvider`, modo compacto `include_full_hourly`, cache com TTL, validação estrita, headers de segurança e suíte `pytest` + `ruff` + `mypy` + `bandit`.
3. **Etapa 3 (Concluída) — Lembretes e Motor de Notificações Backend (Zero PII)**: modelo SQLAlchemy 2.0 `Reminder`, capability token anti-IDOR (`X-Reminder-Token` com hash SHA-256 e `hmac.compare_digest`), criptografia Fernet para `PushSubscription`, anti-SSRF rigoroso para endpoints de push (allowlist de provedores + bloqueio de IPs privados/loopback/DNS rebinding), endpoints `/api/v1/reminders`, `APScheduler` com deduplicação e filtro de chuva, disparo via `pywebpush` (VAPID) com *hard delete* em `404`/`410`, e suíte completa de testes offline.
4. **Etapa 4 (Concluída) — Frontend Multiplataforma (Web + PWA)**: interface mobile-first clara/escura em React + TypeScript + Tailwind com destaque para **3 dias (72h)** (gráfico SVG de temperatura/sensação/chuva + carrossel horário), expansão **até 16 dias** sob demanda, qualidade do ar, favoritos e snapshot offline locais, tela de lembretes, Service Worker (`sw.js`) com Web Push VAPID, `manifest.webmanifest`, ícones PWA e suíte Vitest + TypeScript strict.
5. **Etapa 5 — Empacotamento Android e Preparo iOS (Capacitor)**: integração `@capacitor/local-notifications` com fila deslizante (limite 64 no iOS), `@capacitor/geolocation`, build APK no Debian 13, guia `DEBIAN_SETUP.md` e workflow GitHub Actions para iOS.
6. **Etapa 6 — Camada de IA Climática em Python**: implementação de analisador em `backend/app/services/ai/` para resumos inteligentes, alertas proativos de mudança brusca de tempo, recomendação de vestuário/atividades e insights horários baseados nos dados históricos/futuros.
