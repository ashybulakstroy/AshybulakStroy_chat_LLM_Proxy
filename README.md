# AshybulakStroy AI HUB

Р›С‘РіРєРѕРµ, СѓРґРѕР±РЅРѕРµ, РЅР°РіР»СЏРґРЅРѕРµ Рё Р±С‹СЃС‚СЂРѕРµ СЂРµС€РµРЅРёРµ РґР»СЏ РїСЂРѕРєСЃРёСЂРѕРІР°РЅРёСЏ OpenAI-СЃРѕРІРјРµСЃС‚РёРјС‹С… LLM API. РџСЂРѕСЃС‚РѕР№ FastAPI-РіРµР№С‚РІРµР№ РѕР±СЉРµРґРёРЅСЏРµС‚ chat/completions, embeddings Рё models, РїРѕРґРґРµСЂР¶РёРІР°РµС‚ РјСѓР»СЊС‚РёРїСЂРѕРІР°Р№РґРµСЂРЅРѕСЃС‚СЊ, health-check, Р»РёРјРёС‚С‹ Рё РїРѕРЅСЏС‚РЅС‹Р№ РєРѕРЅС‚СЂРѕР»СЊ СЃРѕСЃС‚РѕСЏРЅРёСЏ.

## РЎС‚РµРє

- Python 3.11+
- FastAPI
- HTTPX
- Pydantic

## Р§С‚Рѕ СЂРµР°Р»РёР·РѕРІР°РЅРѕ

- `/health` вЂ” РїСЂРѕРІРµСЂРєР° СЂР°Р±РѕС‚РѕСЃРїРѕСЃРѕР±РЅРѕСЃС‚Рё
- `/health/limits` вЂ” СЃРІРѕРґРєР° РїРѕ Р»РёРјРёС‚Р°Рј, startup probe Рё РїРѕСЃР»РµРґРЅРёРј РѕС€РёР±РєР°Рј РїСЂРѕРІР°Р№РґРµСЂРѕРІ
- `/health/limits/live` вЂ” РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ startup probe Рё Р»РёРјРёС‚РѕРІ РїРѕ РїСЂРѕРІР°Р№РґРµСЂР°Рј
- `/v1/models` вЂ” СЃРїРёСЃРѕРє РјРѕРґРµР»РµР№ РѕС‚ РїРѕРґРєР»СЋС‡С‘РЅРЅРѕРіРѕ РїСЂРѕРІР°Р№РґРµСЂР°
- `/v1/chat/completions` вЂ” РїСЂРѕРєСЃРё РґР»СЏ chat completions
- `/v1/embeddings` вЂ” РїСЂРѕРєСЃРё РґР»СЏ embeddings

## РўРµРєСѓС‰РµРµ СЃРѕСЃС‚РѕСЏРЅРёРµ

РЎРµР№С‡Р°СЃ РїСЂРѕРµРєС‚ СЂР°Р±РѕС‚Р°РµС‚ РєР°Рє OpenAI-СЃРѕРІРјРµСЃС‚РёРјС‹Р№ РїСЂРѕРєСЃРё Рё СѓРјРµРµС‚ РѕС‚РїСЂР°РІР»СЏС‚СЊ Р·Р°РїСЂРѕСЃ СЃСЂР°Р·Сѓ РІ РЅРµСЃРєРѕР»СЊРєРѕ РїСЂРѕРІР°Р№РґРµСЂРѕРІ, РІС‹Р±РёСЂР°СЏ РїРµСЂРІС‹Р№ СѓСЃРїРµС€РЅС‹Р№ РѕС‚РІРµС‚:

- `PORT`
- `ENABLE_PROVIDER_LOG`
- `LOG_LEVEL`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `GEMINI_API_KEY`
- `SAMBANOVA_API_KEY`
- `EDENAI_API_KEY`
- `FIREWORKS_API_KEY`

РџРѕР»СЏ `provider` Рё `metadata` СѓР¶Рµ РµСЃС‚СЊ РІ СЃС…РµРјР°С… Р·Р°РїСЂРѕСЃРѕРІ Рё РјРѕРіСѓС‚ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊСЃСЏ РїСЂРё РґР°Р»СЊРЅРµР№С€РµРј СЂР°СЃС€РёСЂРµРЅРёРё РјР°СЂС€СЂСѓС‚РёР·Р°С†РёРё.

## Р—Р°РїСѓСЃРє

1. РЈСЃС‚Р°РЅРѕРІРёС‚Рµ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё:

```bash
python -m pip install -r requirements.txt
```

2. РЎРѕР·РґР°Р№С‚Рµ С„Р°Р№Р» `.env` СЃ РїРµСЂРµРјРµРЅРЅС‹РјРё:

```env
PORT=8800
ENABLE_PROVIDER_LOG=true
LOG_LEVEL=INFO

GROQ_API_KEY=your_groq_api_key
GROQ_API_BASE=https://api.groq.com/openai/v1

OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_API_BASE=https://openrouter.ai/api/v1

CEREBRAS_API_KEY=your_cerebras_api_key
CEREBRAS_API_BASE=https://api.cerebras.ai/v1

GEMINI_API_KEY=your_gemini_api_key
GEMINI_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai/

SAMBANOVA_API_KEY=your_sambanova_api_key
SAMBANOVA_API_BASE=https://api.sambanova.ai/v1

EDENAI_API_KEY=your_edenai_api_key
EDENAI_API_BASE=https://api.edenai.run/v3/llm

FIREWORKS_API_KEY=your_fireworks_api_key
FIREWORKS_API_BASE=https://api.fireworks.ai/inference/v1
```

Р•СЃР»Рё Р·Р°РїРѕР»РЅРµРЅРѕ РЅРµСЃРєРѕР»СЊРєРѕ РєР»СЋС‡РµР№, СЃРµСЂРІРёСЃ РѕС‚РїСЂР°РІРёС‚ Р·Р°РїСЂРѕСЃ РІРѕ РІСЃРµ РґРѕСЃС‚СѓРїРЅС‹Рµ РїСЂРѕРІР°Р№РґРµСЂС‹ Рё РІРµСЂРЅС‘С‚ РїРµСЂРІС‹Р№ СѓСЃРїРµС€РЅС‹Р№ РѕС‚РІРµС‚.

Р’ Р»РѕРіР°С… РІРёРґРЅРѕ:

- РЅР° РєР°РєРѕРј РїРѕСЂС‚Сѓ РїРѕРґРЅСЏР»СЃСЏ СЃРµСЂРІРµСЂ
- РІ РєР°РєРѕР№ РїСЂРѕРІР°Р№РґРµСЂ СѓС€С‘Р» Р·Р°РїСЂРѕСЃ
- РєР°РєРѕР№ HTTP-РєРѕРґ РІРµСЂРЅСѓР»СЃСЏ
- СЃРєРѕР»СЊРєРѕ Р·Р°РЅСЏР» Р·Р°РїСЂРѕСЃ
- РґРµС‚Р°Р»Рё РѕС€РёР±РєРё, РµСЃР»Рё РїСЂРѕРІР°Р№РґРµСЂ РѕС‚РІРµС‚РёР» СЃ РѕС€РёР±РєРѕР№ РёР»Рё РЅРµ РѕС‚РІРµС‚РёР»

## РР·РІРµСЃС‚РЅС‹Рµ Р»РёРјРёС‚С‹

- `Groq`: `30 RPM`
- `Cerebras`: `30 RPM`
- `OpenRouter` РґР»СЏ `:free` РјРѕРґРµР»РµР№: `20 RPM`
- `Gemini 2.5 Flash` РЅР° `free tier`: `10 RPM`
- `SambaNova` РЅР° `free tier` РїРѕ СЂР°Р±РѕС‡РµР№ РѕС†РµРЅРєРµ: `20 RPM`
- Р•СЃР»Рё РїСЂРѕРІР°Р№РґРµСЂ РЅРµ РїСЂРёСЃС‹Р»Р°РµС‚ rate-limit headers, СЃРµСЂРІРёСЃ РёСЃРїРѕР»СЊР·СѓРµС‚ Р±РµР·РѕРїР°СЃРЅС‹Р№ fallback: `1 RPM`
- РџСЂРё СЃС‚Р°СЂС‚Рµ РїСЂРёР»РѕР¶РµРЅРёСЏ СЃРµСЂРІРёСЃ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РґРµР»Р°РµС‚ probe РїРѕ РїСЂРѕРІР°Р№РґРµСЂР°Рј, С‡С‚РѕР±С‹ Р·Р°РїРѕР»РЅРёС‚СЊ `/health` Р»РёРјРёС‚Р°РјРё Р±РµР· СЂСѓС‡РЅРѕРіРѕ Р·Р°РїСЂРѕСЃР°
- РџРѕРґСЂРѕР±РЅР°СЏ РѕС†РµРЅРєР° СЃРѕС…СЂР°РЅРµРЅР° РІ С„Р°Р№Р»Р°С… `PROVIDER_LIMITS.md` Рё `provider_limits.json`

3. Р—Р°РїСѓСЃС‚РёС‚Рµ СЃРµСЂРІРёСЃ:

```bash
python run.py
```

РџРѕСЃР»Рµ Р·Р°РїСѓСЃРєР° РјРѕР¶РЅРѕ СЃСЂР°Р·Сѓ СЃРјРѕС‚СЂРµС‚СЊ:

```bash
curl http://localhost:8800/health
curl http://localhost:8800/health/limits
curl -X POST http://localhost:8800/health/limits/live
```

`/health/limits` РїРѕРєР°Р·С‹РІР°РµС‚:

- РєР°РєРёРµ РїСЂРѕРІР°Р№РґРµСЂС‹ Р°РєС‚РёРІРЅС‹
- СЃРєРѕР»СЊРєРѕ РёС… РІСЃРµРіРѕ
- РєРѕРіРґР° Р±С‹Р» РїРѕСЃР»РµРґРЅРёР№ startup probe
- РєР°РєРёРµ РїСЂРѕРІР°Р№РґРµСЂС‹ РѕС‚РІРµС‚РёР»Рё СѓСЃРїРµС€РЅРѕ РЅР° СЃС‚Р°СЂС‚Рµ
- РєР°РєРёРµ РїСЂРѕРІР°Р№РґРµСЂС‹ РІРµСЂРЅСѓР»Рё РѕС€РёР±РєСѓ РЅР° СЃС‚Р°СЂС‚Рµ
- СЂРµР°Р»СЊРЅС‹Рµ Р»РёРјРёС‚С‹ РёР· response headers, РµСЃР»Рё РїСЂРѕРІР°Р№РґРµСЂ РёС… РїСЂРёСЃР»Р°Р»
- fallback `1 RPM`, РµСЃР»Рё РїСЂРѕРІР°Р№РґРµСЂ Р»РёРјРёС‚С‹ РЅРµ РїСЂРёСЃР»Р°Р»

`/health/limits/live` РїРѕР»РµР·РµРЅ, РєРѕРіРґР° РЅСѓР¶РЅРѕ РІСЂСѓС‡РЅСѓСЋ РїРµСЂРµСЃРЅСЏС‚СЊ СЃРІРµР¶РёРµ Р»РёРјРёС‚С‹ Рё СЃС‚Р°С‚СѓСЃ startup probe Р±РµР· РїРµСЂРµР·Р°РїСѓСЃРєР° СЃРµСЂРІРёСЃР°.

## РџСЂРёРјРµСЂ Р·Р°РїСЂРѕСЃР°

```bash
curl http://localhost:8800/v1/chat/completions -X POST \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"РџСЂРёРІРµС‚"}]}'
```

## P2P MVP

The repository now contains a separate P2P debug/MVP layer for future `MASTER` and `PEER` orchestration.

Current MVP scope:

- node runtime mode: `peer`, `master`, `master_cache`, `auto`
- P2P enable/disable runtime control
- separate P2P debug admin page
- peer heartbeat/debug registration
- peer registry in memory
- peer capabilities:
  - chat support
  - embeddings support
  - providers list
  - models list
  - health score
- session counters for incoming/outgoing/queued P2P work
- dispatch preview for P2P selection
- network map summary:
  - masters count
  - master direct provider links count
  - peers count
  - peer direct provider links count
  - direct peers vs link-only peers
  - direct provider links across the network
  - unique routes by 12-char hash
  - redundant routes by duplicate hash
- P2P logs with `p2p_...` prefixes

Direct route capacity rules:

- if a node has its own keys and reaches provider APIs directly, it is counted as `direct_provider_access=true`
- if a node only points to another master/peer and does not own provider access, it is treated as `link-only`
- `Network Map` capacity is now based only on direct provider links
- `dispatch preview` skips link-only peers because they do not add real route capacity in the current MVP

Current master recovery flow:

- master saves current peer/network state to `p2p_network_snapshot.json`
- on startup master loads that snapshot back into memory
- after startup master asks saved peers to re-register through `/internal/p2p/re-register`
- peer then sends a fresh heartbeat back to the master

Recommended config for peers:

- set `P2P_BASE_URL` to the real reachable URL of that node
- set `P2P_MASTER_URL` to the master URL
- this helps master re-register peers correctly after restart

Slot-based sharing limits:

- `P2P_MAX_CLIENT_SLOTS_PER_MIN=1` limits how many LLM slot units one client may consume per minute on a node
- `P2P_MAX_SHARED_SLOTS_PER_MIN=5` limits how many slot units the node is willing to share with the whole P2P network per minute
- `P2P_ROUTE_TTL_MIN=1440` defines how long a non-working route may stay in memory/snapshot before it is cleared
- every direct route now gets `route_id = sha256(api_key + provider + model)[:12]`
- `Маршрутизация` shows `Route ID` and `Resource`
- route slots are now calculated as:
  - `ceil(P2P_MAX_SHARED_SLOTS_PER_MIN / resources_in_node)`

Main endpoints:

- `/admin/p2p`
- `/admin/p2p/status`
- `/admin/p2p/peers`
- `/admin/p2p/dispatch/preview`

Admin layout notes:

- `Known Peers` is rendered right after `Network Map`
- peer table shows route type: `direct` or `link-only`

Important limitation:

- real remote P2P execution is not implemented yet
- current P2P layer is a selection/debug MVP, not full peer-to-peer transport

Main files:

- `app/p2p_service.py`
- `app/p2p_admin_ui.py`
- `P2P_SUBPROJECT_SPEC.md`

## Р”Р°Р»СЊС€Рµ РјРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ

- РјР°СЂС€СЂСѓС‚РёР·Р°С†РёСЋ РјРµР¶РґСѓ РЅРµСЃРєРѕР»СЊРєРёРјРё РїСЂРѕРІР°Р№РґРµСЂР°РјРё
- API-РєР»СЋС‡Рё РєР»РёРµРЅС‚РѕРІ
- СЂРµС‚СЂР°Рё, РєРµС€ Рё Р»РѕРіРёСЂРѕРІР°РЅРёРµ
- С‚РµСЃС‚С‹ Рё CI

________________________________________________________________________________
                   [ MASTER NODE (Discovery & Registry) ]
          /--------------------------|--------------------------\
         /            (Sync: Peer List / Health Check)           \
        /                            |                            \
 [ PEER NODE #1 ]            [ PEER NODE #2 ]            [ MASTER_CACHE ]
 | - API Keys   | <---P2P---> | - API Keys   | <---P2P---> | - No Keys    |
 | - LLM Access |   Traffic   | - LLM Access |   Traffic   | - Stats Only |
 \______+_______/             \______+_______/             \______+_______/
        |                            |                            |
  (Proxy Requests)             (Proxy Requests)             (Routing Only)
        |                            |                            |
  [ PROVIDERS ]                [ PROVIDERS ]                [ NETWORK MAP ]
  (OpenAI/Anth)                (Local/Ollama)               (Active Peers)
________________________________________________________________________________

   Р›Р•Р“Р•РќР”Рђ:
   * MASTER:       РўРѕС‡РєР° СЂРµРіРёСЃС‚СЂР°С†РёРё. Р’Р°Р»РёРґРёСЂСѓРµС‚ РЅРѕРґС‹ Рё СЂР°Р·РґР°РµС‚ СЃРїРёСЃРєРё.
   * PEER:         РЈР·РµР» СЃ РєР»СЋС‡Р°РјРё. РСЃРїРѕР»РЅСЏРµС‚ Р·Р°РїСЂРѕСЃС‹ Рё РґРµР»РёС‚СЃСЏ РјРѕС‰РЅРѕСЃС‚СЊСЋ.
   * MASTER_CACHE: "Р“РѕР»С‹Р№" СЃРµСЂРІРµСЂ (EMPTY). РќРµ РёРјРµРµС‚ РєР»СЋС‡РµР№, РЅРѕ Р·РЅР°РµС‚ РїСѓС‚СЊ Рє РЅРёРј.
   * P2P Traffic:  РЎР»СѓР¶РµР±РЅС‹Рµ СЃРѕРѕР±С‰РµРЅРёСЏ (Gossip) Рѕ РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё РјРѕРґРµР»РµР№.
________________________________________________________________________________

________________________________________________________________________________
[ РђР РҐРРўР•РљРўРЈР Рђ РЎР•РўР AshybulakStroy AI HUB ] (Width: 80 chars)
________________________________________________________________________________

       [ MASTER NODE ] (Registry & Discovery)
              |
              |-- (1) Р РµРіРёСЃС‚СЂР°С†РёСЏ & Health Check (Ping/Pong)
              |-- (2) Р Р°СЃСЃС‹Р»РєР° Р±РµР»РѕРіРѕ СЃРїРёСЃРєР° (Peer Sync)
              V
   /-----------------------\           /-----------------------\
   |   [ MASTER_CACHE ]    |           |      [ PEER NODE ]    |
   | (Empty / Consumer)    |---(3)---->|  (Provider / Node)    |
   |-----------------------|   P2P     |-----------------------|
   | - РќРµС‚ РєР»СЋС‡РµР№          |  Request  | - Р•СЃС‚СЊ API РєР»СЋС‡Рё      |
   | - РљР°СЂС‚Р° СЃРµС‚Рё (Peers)  |           | - Р РµРїСѓС‚Р°С†РёСЏ РІ HUB     |
   \___________+___________/           \___________+___________/
               |                                   |
               | (4) РџРµСЂРµРЅР°РїСЂР°РІР»РµРЅРёРµ               | (5) Р’С‹Р·РѕРІ РјРµС‚РѕРґР°
               V                                   V
   /-----------------------\           /-----------------------\
   |   [ LLM РћРџР•Р РђРўРћР  ]    |           |   [ LLM РћРџР•Р РђРўРћР  ]    |
   |   (Proxy Layer)       |           |   (Execution Layer)   |
   |-----------------------|           |-----------------------|
   | - РџСЂРёРЅРёРјР°РµС‚ API Р·Р°РїСЂ. |           | - Р¤РѕСЂРјР°С‚РёСЂСѓРµС‚ РїСЂРѕРјРїС‚  |
   | - Р’С‹Р±РёСЂР°РµС‚ Р¶РёРІРѕР№ Peer |           | - Р Р°Р±РѕС‚Р°РµС‚ СЃ OpenAI/..|
   \_______________________/           \___________+___________/
               ^                                   |
               | (0) Р’С…РѕРґСЏС‰РёР№ Р·Р°РїСЂРѕСЃ               | (6) РћС‚РІРµС‚ (JSON)
          [ РљР›РР•РќРў ] <-----------------------------/

________________________________________________________________________________

РљР РђРўРљРћР• РћРџРРЎРђРќРР• Р РћР›Р•Р™:

* MASTER:        Р“Р»Р°РІРЅС‹Р№ СЃСѓРґСЊСЏ. Р—РЅР°РµС‚, РєС‚Рѕ РІ СЃРµС‚Рё "Р¶РёРІРѕР№" Рё Сѓ РєРѕРіРѕ РєР°РєРёРµ РјРѕРґРµР»Рё.
* PEER:          Р Р°Р±РѕС‡Р°СЏ Р»РѕС€Р°РґРєР°. РРјРµРµС‚ РєР»СЋС‡Рё Рё СЂРµР°Р»СЊРЅРѕ РёСЃРїРѕР»РЅСЏРµС‚ Р·Р°РїСЂРѕСЃС‹.
* MASTER_CACHE:  "Р’С…РѕРґРЅР°СЏ РґРІРµСЂСЊ". РџСЂРёРЅРёРјР°РµС‚ Р·Р°РїСЂРѕСЃС‹, РЅРѕ СЃР°Рј РёС… РЅРµ РґРµР»Р°РµС‚, 
                 Р° РїРµСЂРµРєРёРґС‹РІР°РµС‚ РЅР° СЃРІРѕР±РѕРґРЅС‹Рµ PEER-РЅРѕРґС‹.
* LLM РћРџР•Р РђРўРћР :  РџСЂРѕРіСЂР°РјРјРЅС‹Р№ СЃР»РѕР№ РІРЅСѓС‚СЂРё РєР°Р¶РґРѕРіРѕ СѓР·Р»Р°. РћРЅ РѕС‚РІРµС‡Р°РµС‚ Р·Р° "СЏР·С‹Рє"
                 РѕР±С‰РµРЅРёСЏ (OpenAI API С„РѕСЂРјР°С‚) Рё Р»РѕРіРёРєСѓ СЂР°Р±РѕС‚С‹ СЃ РїСЂРѕРІР°Р№РґРµСЂР°РјРё.
________________________________________________________________________________

================================================================================
================================================================================

   ##       ##       ###      ###         ######     #####     ###### 
   ##       ##       ####    ####         ##   ##   ##   ##    ##   ##
   ##       ##       ## ##  ## ##         ##   ##        ##    ##   ##
   ##       ##       ##  ## ## ##         ######        ##     ###### 
   ##       ##       ##   ###  ##         ##           ##      ##     
   ##       ##       ##        ##         ##          ##       ##     
   #######  #######  ##        ##         ##         ######    ##     

               ##   ##  ##   ##  ######                 
               ##   ##  ##   ##  ##   ##                
               ##   ##  ##   ##  ##   ##                
               #######  ##   ##  ######                 
               ##   ##  ##   ##  ##   ##                
               ##   ##  ##   ##  ##   ##                
               ##   ##   #####   ######                 

================================================================================
================ [ ASHYBULAKSTROY AI HUB v1.0 ] ================
================================================================================

