# AGENTS.md — Guia Operacional de Desenvolvimento e Segurança (ClimaPy)

> Este documento define as regras obrigatórias para qualquer agente de IA ou pessoa desenvolvedora atuando neste repositório.

---

## 1. Regra Inicial Obrigatória

1. **Leia `CONTEXT.md` integralmente** antes de planejar ou alterar qualquer arquivo.
2. **Trabalhe estritamente por etapas**: nunca implemente funcionalidades de etapas futuras sem confirmação explícita do usuário, e nunca avance decisões arquiteturais abertas (como escolha da stack de UI na ADR-001) sem validação prévia.
3. **Mantenha `CONTEXT.md` atualizado**: sempre que uma decisão técnica evoluir ou uma etapa for concluída, atualize o `CONTEXT.md` no mesmo ciclo.

---

## 2. Guardrails Invioláveis de Segurança e Privacidade

Qualquer código que viole as regras abaixo **não deve ser aceito nem considerado concluído**:

1. **Zero SQL Injection**:
   - Use exclusivamente **SQLAlchemy 2.0 ORM / Core com parâmetros vinculados (`bind parameters`)**.
   - **Proibido** concatenar strings, usar f-strings, `%` ou `.format()` em qualquer consulta SQL.
2. **Zero Segredos ou Dados Sensíveis no Código**:
   - **Nunca** faça commit ou hardcode de chaves de API, chaves privadas VAPID, chaves Fernet, senhas, arquivos `.env`, `*.pem`, `*.key`, `*.jks`, `*.keystore` ou `google-services.json`.
   - Toda configuração sensível deve vir de variáveis de ambiente carregadas via `pydantic-settings`.
   - Mantenha `.env.example` sempre atualizado, porém contendo apenas placeholders vazios ou valores fictícios seguros.
3. **Zero Login, Zero Contas e Zero PII**:
   - **Não implemente** cadastro, login, coleta de e-mail, telefone, nome completo, CPF ou cookies de rastreamento/analytics invasivos.
   - Coordenadas enviadas ao backend ou gravadas em cache/lembretes devem ser arredondadas para **2 casas decimais (~1,1 km)** para preservar a privacidade sem perder precisão meteorológica.
4. **Anti-IDOR Obrigatório em Lembretes (Sem Conta)**:
   - Toda criação de lembrete no servidor deve gerar um capability token criptograficamente aleatório (`secrets.token_urlsafe(32)`), persistir **apenas o hash SHA-256** no banco e validar operações de leitura/edição/exclusão via header `X-Reminder-Token` com `hmac.compare_digest`.
5. **Criptografia de Subscriptions Web Push**:
   - O payload de `PushSubscription` (`endpoint`, `p256dh`, `auth`) nunca deve ser salvo em texto plano nem logado; armazene sempre cifrado com **Fernet** (`cryptography`).
6. **Proteção Anti-SSRF Obrigatória**:
   - Toda requisição HTTP de saída para APIs de clima/geocoding deve passar por uma **allowlist fixa de URLs/domínios HTTPS** e usar `follow_redirects=False`.
   - Todo `endpoint` recebido em `PushSubscription` deve ser validado quanto a esquema `https://`, domínio compatível com provedores Web Push legítimos e **bloqueio explícito de IPs privados, loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`) e redes reservadas**.
7. **Validação Estrita, XSS e Hardening HTTP**:
   - Valide todos os inputs no backend com **Pydantic v2** (limites de lat/lon, range de dias `1..16`, fusos horários válidos em `zoneinfo.available_timezones()`, tamanho máximo e sanitização de strings).
   - No frontend, **é proibido** usar `dangerouslySetInnerHTML`, `innerHTML`, `eval()` ou renderização de HTML não confiável.
   - Mantenha middlewares de rate limiting (`slowapi`), CORS explícito por lista de origens e headers de segurança (`Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).
   - **Sanitização de logs**: nunca grave tokens, segredos, payloads de `PushSubscription` ou IPs completos desnecessários em logs.

---

## 3. Padrões de Código e Arquitetura

### 3.1 Backend Python (3.12)
- **Assíncrono por padrão**: use `async/await` com `httpx.AsyncClient` e **timeouts explícitos** (connect/read/total) em todas as chamadas externas.
- **Provider / Adapter Pattern**: mantenha provedores desacoplados em `backend/app/providers/` implementando um contrato único (`WeatherProvider`).
  - `OpenMeteoProvider`: primário (até 16 dias horários + Geocoding PT + Air Quality).
  - `MetNorwayProvider`: fallback automático (exige header `User-Agent` configurável).
  - `WeatherAPIProvider`: opcional, ativado apenas se `WEATHERAPI_KEY` estiver presente no `.env`.
- **Arquitetura em Camadas**:
  - `api/v1/`: validação de entrada/saída HTTP e status codes (sem regra de negócio pesada).
  - `services/`: orquestração, cache, fallback, agendamento e notificações.
  - `providers/`: comunicação externa e tradução para os schemas internos.
  - `models/` e `schemas/`: separação estrita entre modelos ORM do banco e contratos Pydantic da API.
- **Camada de IA Desacoplada (`backend/app/services/ai/`)**:
  - Defina interfaces claras (`WeatherAnalyzer`) que recebam apenas os DTOs meteorológicos normalizados e retornem análises estruturadas.
  - A IA nunca deve bloquear o carregamento básico da previsão do tempo (execução opcional/assíncrona com fallback seguro).
- **Estilo e Tipagem**: type hints completos em todas as funções públicas, docstrings concisas e conformidade com `ruff` e `mypy`.

### 3.2 Frontend Multiplataforma
- **Mobile-first e Acessível**: layout responsivo pensado para telas de celular primeiro, com suporte a **tema claro e escuro**, alto contraste e navegação limpa entre **3 dias (72h)** e **até 16 dias**.
- **Atribuição Obrigatória**: manter crédito visível e discreto das fontes gratuitas utilizadas (*Open-Meteo*, *MET Norway*, *OpenStreetMap* quando aplicável).
- **Resiliência Offline**: exibir última previsão em cache local com indicação clara de horário de atualização caso o dispositivo esteja sem internet.
- **Notificações por Plataforma**:
  - Em app nativo (Capacitor Android/iOS), priorizar notificações locais agendadas com gerenciamento de fila em janela deslizante (respeitando o teto de 64 pendentes no iOS).
  - Em Web/PWA, utilizar Service Worker + Web Push VAPID anônimo.

---

## 4. Regras para o Ambiente Debian 13 (Trixie)

1. **Respeite a PEP 668**: nunca instale pacotes Python globalmente com `pip install` no sistema do Debian 13. Utilize sempre o ambiente virtual isolado em Python `3.12.16` via `uv` (`--python-preference only-managed`) em `backend/.venv`, evitando `/usr/local/bin/python3.12` (`3.12.0` compilado com GCC 14.2.0 + `--enable-optimizations`, que apresenta `SIGSEGV` ao compilar bytecode).
2. **Transparência de Dependências de Sistema**: sempre que uma etapa exigir pacotes nativos do Debian (ex.: `openjdk-17-jdk`, `python3-venv`, Android SDK), documente os comandos exatos em `docs/DEBIAN_SETUP.md` antes de utilizá-los.
3. **Compatibilidade Multi-SO**: mantenha o código e scripts compatíveis com Linux (Debian 13) para desenvolvimento, testes, Web e build Android, e forneça pipeline reproduzível (GitHub Actions `macos-latest`) para builds iOS (`.ipa`), deixando claro que o Xcode não roda nativamente no Linux.

---

## 5. Definition of Done (Checklist por Etapa)

Uma etapa só pode ser considerada concluída quando **todos** os itens aplicáveis forem verificados:

1. **Testes Automatizados (`pytest`)**:
   - Testes unitários e de integração passando 100%, com chamadas externas às APIs de clima e push devidamente mockadas (testes não podem depender de acesso à internet).
   - Cobertura obrigatória de casos de segurança (rejeição de coordenadas inválidas, proteção anti-SSRF, bloqueio anti-IDOR sem/com token inválido, verificação de queries parametrizadas).
2. **Qualidade e Análise Estática**:
   - `ruff check` e `ruff format --check` sem erros.
   - Verificação de tipos (`mypy`) limpa nos módulos backend (e `tsc --noEmit` no frontend a partir da Etapa 4).
   - Auditoria estática de segurança Python com `bandit` sem alertas críticos/médios não justificados.
3. **Auditoria de Segredos**:
   - Conferir `git status` e buscar possíveis chaves/segredos acidentais antes de finalizar a etapa; garantir que `.env` continua ignorado pelo `.gitignore`.
4. **Documentação Sincronizada**:
   - `CONTEXT.md` (e `docs/DEBIAN_SETUP.md` quando aplicável) atualizado refletindo exatamente o que foi implementado e testado.
