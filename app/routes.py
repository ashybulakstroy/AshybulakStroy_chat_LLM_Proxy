import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.config import settings
from app.rate_limits import rate_limit_store
from app.router_service import ProviderRouter, UpstreamProvidersExhausted
from app.schemas import ChatCompletionRequest, EmbeddingRequest

router = APIRouter()
provider_router = ProviderRouter()
LIMITS_FILE = Path(__file__).resolve().parent.parent / "provider_limits.json"
MODEL_VALIDATION_FILE = Path(__file__).resolve().parent.parent / "model_validation_snapshot.json"
ADMIN_CACHE_FILE = Path(__file__).resolve().parent.parent / "admin_dashboard_cache.json"
PREFERRED_TEST_MODELS = {
    "groq": ["llama-3.1-8b-instant", "qwen/qwen3-32b"],
    "openrouter": ["qwen/qwen3.6-plus-preview:free", "openai/gpt-5.4-mini"],
    "cerebras": ["llama3.1-8b", "qwen-3-235b-a22b-instruct-2507"],
    "gemini": ["models/gemini-2.5-flash", "models/gemini-2.0-flash"],
    "sambanova": ["DeepSeek-V3.2", "DeepSeek-V3.1"],
}
GROQ_EXCLUDED_PREFIXES = ("canopylabs/orpheus",)
GEMINI_FREE_TIER_PREFIXES = (
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemma-",
)
TEST_PROMPT = "Ассаламу алейкум!. Верни Уа Алейкум Ассалам!"
EXPECTED_TEST_REPLY = "уа алейкум ассалам"

TEST_PROMPT = "Ассаламу алейкум!. Верни Уа Алейкум Ассалам!"
EXPECTED_TEST_REPLIES = {
    "ва алейкум ассалам",
    "ва алейкум асс салам",
    "وعليكم السلام",
}
VALIDATED_LLM_JOB_STATE = {
    "status": "idle",
    "running": False,
    "requests_started": 0,
    "responses_received": 0,
    "total_models": 0,
    "passed": 0,
    "failed": 0,
    "started_by": None,
    "last_started_at": None,
    "last_finished_at": None,
    "error": None,
}
VALIDATED_LLM_JOB_TASK: asyncio.Task | None = None

ADMIN_PAGE_HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Ashybulak AI Connect Admin</title>
  <style>
    :root {
      --bg: #f5f0e6;
      --paper: #fff9ef;
      --ink: #1f2d2b;
      --muted: #6c756f;
      --line: #d9d2c5;
      --accent: #0f766e;
      --accent-2: #9a6700;
      --good: #166534;
      --warn: #9a6700;
      --bad: #b91c1c;
      --shadow: 0 14px 36px rgba(31, 45, 43, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15,118,110,0.10), transparent 28%),
        radial-gradient(circle at top right, rgba(154,103,0,0.12), transparent 24%),
        linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
    }
    .wrap {
      max-width: 1400px;
      margin: 0 auto;
      padding: 28px 18px 40px;
    }
    .hero {
      display: grid;
      gap: 10px;
      margin-bottom: 18px;
    }
    .eyebrow {
      color: var(--accent);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-weight: 700;
    }
    h1 {
      margin: 0;
      font-size: clamp(28px, 4vw, 52px);
      line-height: 0.95;
    }
    .lead {
      margin: 0;
      color: var(--muted);
      max-width: 900px;
      font-size: 16px;
      line-height: 1.5;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 6px;
      align-items: center;
    }
    button {
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      font: inherit;
      cursor: pointer;
      color: white;
      background: var(--accent);
      box-shadow: var(--shadow);
    }
    button.secondary { background: var(--accent-2); }
    .refresh-control {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 249, 239, 0.9);
      color: var(--muted);
      box-shadow: var(--shadow);
      font-size: 14px;
    }
    .refresh-control select {
      border: 0;
      background: transparent;
      color: var(--ink);
      font: inherit;
      outline: none;
    }
    .panel {
      background: rgba(255, 249, 239, 0.94);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 18px;
      box-shadow: var(--shadow);
      margin-bottom: 16px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 10px;
    }
    .stat {
      background: rgba(15,118,110,0.05);
      border: 1px solid rgba(15,118,110,0.12);
      border-radius: 16px;
      padding: 12px;
    }
    .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }
    .value {
      font-size: 24px;
      font-weight: 700;
    }
    .sub {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
      margin-top: 4px;
    }
    .table-wrap {
      overflow: auto;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.55);
    }
    .group-stack {
      display: grid;
      gap: 16px;
    }
    .group-title {
      margin: 0 0 10px;
      font-size: 24px;
      line-height: 1.1;
    }
    .group-sub {
      color: var(--muted);
      font-size: 13px;
      margin: 0 0 12px;
    }
    .loading-box {
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid rgba(15,118,110,0.18);
      background: rgba(15,118,110,0.06);
      color: var(--accent);
      font-size: 14px;
      margin-bottom: 12px;
    }
    .progress-stack {
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }
    .progress-line {
      display: grid;
      gap: 6px;
    }
    .progress-meta {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 13px;
      color: var(--muted);
    }
    .progress-track {
      width: 100%;
      height: 12px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(15,118,110,0.10);
      border: 1px solid rgba(15,118,110,0.12);
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--accent), #4aa39c);
      transition: width 0.25s ease;
    }
    .recommendations {
      display: grid;
      gap: 10px;
    }
    .recommendation {
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.58);
    }
    .recommendation-title {
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 6px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 980px;
    }
    th, td {
      padding: 12px 10px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid var(--line);
      font-size: 14px;
      line-height: 1.35;
    }
    th {
      position: sticky;
      top: 0;
      background: #f7f1e6;
      z-index: 1;
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--muted);
    }
    tr.warn { background: rgba(250, 204, 21, 0.08); }
    tr.error { background: rgba(248, 113, 113, 0.10); }
    tr.trend-up { background: rgba(34, 197, 94, 0.12); }
    tr.trend-down { background: rgba(239, 68, 68, 0.12); }
    .pill {
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      font-size: 12px;
      background: rgba(15,118,110,0.10);
      color: var(--accent);
      white-space: nowrap;
    }
    .status-ok { color: var(--good); }
    .status-warn { color: var(--warn); }
    .status-error { color: var(--bad); }
    .trend-icon {
      margin-left: 6px;
      font-size: 12px;
      font-weight: 700;
    }
    .trend-up-text { color: var(--good); }
    .trend-down-text { color: var(--bad); }
    .mono {
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
    }
    .test-cell {
      min-width: 220px;
    }
    .test-result {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .empty {
      color: var(--muted);
      padding: 18px 4px 4px;
    }
    .hidden-meta {
      display: none;
    }
    @media (max-width: 900px) {
      .stats { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="eyebrow">Админка</div>
      <h1>Ashybulak AI Connect</h1>
      <p class="lead">Одна таблица сверху вниз: каждая строка это модель, а лимиты подтягиваются из live-наблюдений провайдера и сохранённой оценки RPM/RPD.</p>
      <div class="actions">
        <button id="refreshAll">Обновить</button>
        <button id="refreshLive" class="secondary">Обновить live-лимиты</button>
        <label class="refresh-control">
          <span>Автообновление</span>
          <select id="refreshInterval">
            <option value="1">1 мин</option>
            <option value="2">2 мин</option>
            <option value="3" selected>3 мин</option>
            <option value="4">4 мин</option>
            <option value="5">5 мин</option>
          </select>
        </label>
      </div>
    </section>

    <section class="panel">
      <div class="label">Блок №1</div>
      <div class="stats" id="overviewStats"></div>
    </section>

    <section class="panel">
      <div class="label">Блок №2</div>
      <div class="label">Модели и лимиты</div>
      <div id="loadingState" class="loading-box">Идет сбор данных и счетчиков. Подождите...</div>
      <div class="group-stack" id="groupedTables">
      </div>
    </section>

    <section class="panel">
      <div class="label">Блок №3</div>
      <div class="label">Рекомендации от ИИ</div>
      <div id="recommendations" class="recommendations"></div>
    </section>

    <section class="panel">
      <div class="label">Блок №4</div>
      <div class="label">Проверенные модели LLM</div>
      <div class="actions" style="margin-bottom: 12px;">
        <button id="refreshValidatedLlm" class="secondary">Проверить оставшиеся LLM</button>
      </div>
      <div id="validatedLlmState" class="loading-box" style="display:none;"></div>
      <div id="validatedLlmTables"></div>
    </section>
  </div>

  <script>
    const overviewStats = document.getElementById('overviewStats');
    const groupedTables = document.getElementById('groupedTables');
    const refreshInterval = document.getElementById('refreshInterval');
    const loadingState = document.getElementById('loadingState');
    const recommendationsNode = document.getElementById('recommendations');
    const validatedLlmNode = document.getElementById('validatedLlmTables');
    const validatedLlmState = document.getElementById('validatedLlmState');
    let autoRefreshHandle = null;
    let validatedLlmProgressHandle = null;
    const trendStorageKey = 'ashybulak_admin_trends_v1';

    function fmt(value) {
      return value === null || value === undefined || value === '' ? 'n/a' : String(value);
    }

    function percent(current, total) {
      if (!total) return 0;
      return Math.max(0, Math.min(100, Math.round((current / total) * 100)));
    }

    function statCard(label, value, extra = '') {
      return `
        <div class="stat">
          <div class="label">${label}</div>
          <div class="value">${fmt(value)}</div>
          ${extra ? `<div class="sub">${extra}</div>` : ''}
        </div>
      `;
    }

    function observedRpm(item) {
      return item?.limits?.requests?.minute?.limit ?? item?.limits?.rpm ?? null;
    }

    function observedRpd(item) {
      return item?.limits?.requests?.day?.limit ?? item?.limits?.rpd ?? null;
    }

    function remainingRpm(item) {
      return item?.limits?.requests?.minute?.remaining ?? item?.limits?.rpm_remaining ?? null;
    }

    function remainingRpd(item) {
      return item?.limits?.requests?.day?.remaining ?? item?.limits?.rpd_remaining ?? null;
    }

    function remainingTokensMinute(item) {
      return item?.limits?.tokens?.minute?.remaining ?? null;
    }

    function getTrendState() {
      try {
        return JSON.parse(localStorage.getItem(trendStorageKey) || '{}');
      } catch {
        return {};
      }
    }

    function setTrendState(value) {
      localStorage.setItem(trendStorageKey, JSON.stringify(value));
    }

    function trendKey(model) {
      return `${model.provider || 'unknown'}::${model.id || 'unknown'}`;
    }

    function numericOrNull(value) {
      if (value === null || value === undefined || value === '' || value === 'n/a') {
        return null;
      }
      const parsed = Number(value);
      return Number.isNaN(parsed) ? null : parsed;
    }

    function formatGmtPlus5(value) {
      if (!value) return 'n/a';
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return String(value);
      const shifted = new Date(parsed.getTime() + (5 * 60 * 60 * 1000));
      const pad = (n) => String(n).padStart(2, '0');
      return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())} ` +
        `${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}:${pad(shifted.getUTCSeconds())}`;
    }

    function rowStatus(liveItem, estimate) {
      if (liveItem?.last_error) {
        return { text: 'ошибка', cls: 'status-error', row: 'error' };
      }
      if (liveItem?.limits?.source === 'fallback_default') {
        return { text: 'fallback', cls: 'status-warn', row: 'warn' };
      }
      const liveRpm = observedRpm(liveItem);
      if (estimate?.estimated_rpm && liveRpm && String(estimate.estimated_rpm) !== String(liveRpm)) {
        return { text: 'расхождение', cls: 'status-warn', row: 'warn' };
      }
      return { text: 'ok', cls: 'status-ok', row: '' };
    }

    function maxBundle(liveItem, estimate) {
      return {
        maxRpm: observedRpm(liveItem) ?? estimate?.estimated_rpm ?? null,
        maxRpd: observedRpd(liveItem) ?? estimate?.estimated_rpd ?? null,
        maxTpm: liveItem?.limits?.tokens?.minute?.limit ?? null,
      };
    }

    function rowHtml(model, liveItem, estimate, trendInfo) {
      const provider = model.provider || 'unknown';
      const status = rowStatus(liveItem, estimate);
      const maxValues = maxBundle(liveItem, estimate);
      const trendIcon = trendInfo.direction === 'up'
        ? '<span class="trend-icon trend-up-text">↑</span>'
        : trendInfo.direction === 'down'
          ? '<span class="trend-icon trend-down-text">↓</span>'
          : '';
      const rowClass = trendInfo.highlightClass || status.row;
      return `
        <tr class="${rowClass}">
          <td><span class="pill">${fmt(provider)}</span></td>
          <td class="mono">${fmt(model.id)}</td>
          <td>${fmt(remainingRpm(liveItem))}${trendIcon}</td>
          <td>${fmt(remainingRpd(liveItem))}</td>
          <td>${fmt(remainingTokensMinute(liveItem))}</td>
          <td class="hidden-meta">RPM: ${fmt(maxValues.maxRpm)} | RPD: ${fmt(maxValues.maxRpd)} | TPM: ${fmt(maxValues.maxTpm)}</td>
          <td>${fmt(liveItem?.limits?.source)}</td>
          <td class="${status.cls}">${status.text}</td>
          <td class="mono">${formatGmtPlus5(liveItem?.last_observed_at)}</td>
          <td class="test-cell">
            <button data-provider="${provider}" data-model="${fmt(model.id)}">Проверить</button>
            <div class="test-result" id="test-result-${provider}-${fmt(model.id).replace(/[^a-zA-Z0-9_-]/g, '_')}"></div>
          </td>
        </tr>
      `;
    }

    function validatedRowHtml(model) {
      const provider = model.provider || 'unknown';
      const validation = model._validation || {};
      return `
        <tr>
          <td><span class="pill">${fmt(provider)}</span></td>
          <td class="mono">${fmt(model.id)}</td>
          <td>${fmt(validation.message_excerpt)}</td>
          <td class="mono">${formatGmtPlus5(validation.validated_at)}</td>
          <td class="test-cell">
            <button data-provider="${provider}" data-model="${fmt(model.id)}">Проверить</button>
            <div class="test-result" id="test-result-${provider}-${fmt(model.id).replace(/[^a-zA-Z0-9_-]/g, '_')}"></div>
          </td>
        </tr>
      `;
    }

    function categoryForModel(model) {
      const id = String(model?.id || '').toLowerCase();
      const name = String(model?.name || '').toLowerCase();
      const description = String(model?.description || '').toLowerCase();
      const hay = `${id} ${name} ${description}`;

      const audioHints = ['whisper', 'transcribe', 'transcription', 'speech-to-text', 'stt', 'asr', 'audio'];
      const videoHints = ['video', 'veo', 'sora', 'movie', 'clip', 'vision-video', 'gen-video'];

      if (audioHints.some((hint) => hay.includes(hint))) {
        return 'audio';
      }
      if (videoHints.some((hint) => hay.includes(hint))) {
        return 'video';
      }
      if (
        hay.includes('chat') ||
        hay.includes('instruct') ||
        hay.includes('llama') ||
        hay.includes('gpt') ||
        hay.includes('gemini') ||
        hay.includes('qwen') ||
        hay.includes('deepseek') ||
        hay.includes('claude') ||
        hay.includes('mistral') ||
        hay.includes('command') ||
        hay.includes('language') ||
        hay.includes('reason') ||
        hay.includes('completion')
      ) {
        return 'llm';
      }
      return 'other';
    }

    function isOkStatus(liveItem, estimate) {
      return rowStatus(liveItem, estimate).text === 'ok';
    }

    function resourceWeight(model, liveItem) {
      const context = numericOrNull(model?.context_length ?? model?.context_window);
      const completion = numericOrNull(model?.max_completion_tokens ?? model?.top_provider?.max_completion_tokens);
      const liveRpm = numericOrNull(observedRpm(liveItem));
      const liveRpd = numericOrNull(observedRpd(liveItem));
      const hasLive = liveItem?.limits?.source === 'response_headers' ? 1 : 0;
      return {
        hasLive,
        context: context ?? 0,
        completion: completion ?? 0,
        liveRpm: liveRpm ?? 0,
        liveRpd: liveRpd ?? 0,
      };
    }

    function compareModelsByPriority(a, b) {
      const left = a.weight;
      const right = b.weight;
      if (right.hasLive !== left.hasLive) return right.hasLive - left.hasLive;
      if (right.context !== left.context) return right.context - left.context;
      if (right.completion !== left.completion) return right.completion - left.completion;
      if (right.liveRpd !== left.liveRpd) return right.liveRpd - left.liveRpd;
      if (right.liveRpm !== left.liveRpm) return right.liveRpm - left.liveRpm;
      return String(a.model.id).localeCompare(String(b.model.id));
    }

    function recommendationCard(title, text) {
      return `
        <div class="recommendation">
          <div class="recommendation-title">${title}</div>
          <div>${text}</div>
        </div>
      `;
    }

    function buildRecommendations(health, models) {
      const providers = Object.entries(health.limits || {})
        .map(([provider, item]) => ({
          provider,
          source: item?.limits?.source,
          rpmRemaining: numericOrNull(remainingRpm(item)),
          rpdRemaining: numericOrNull(remainingRpd(item)),
          tpmRemaining: numericOrNull(remainingTokensMinute(item)),
        }))
        .filter((item) => item.source === 'response_headers');

      if (!providers.length) {
        return [
          recommendationCard('Живых рекомендаций пока нет', 'Провайдеры ещё не отдали live-счётчики. Нажмите "Обновить live-лимиты" и подождите завершения сбора данных.')
        ].join('');
      }

      const bestByRpm = [...providers].sort((a, b) => (b.rpmRemaining ?? -1) - (a.rpmRemaining ?? -1))[0];
      const lowestByRpm = [...providers].sort((a, b) => (a.rpmRemaining ?? Number.MAX_SAFE_INTEGER) - (b.rpmRemaining ?? Number.MAX_SAFE_INTEGER))[0];
      const bestByTokens = [...providers].sort((a, b) => (b.tpmRemaining ?? -1) - (a.tpmRemaining ?? -1))[0];
      const modelCounts = providers.map((item) => {
        const count = (models.data || []).filter((model) => model.provider === item.provider).length;
        return { provider: item.provider, count };
      }).sort((a, b) => b.count - a.count);

      return [
        recommendationCard(
          'Куда лучше отправлять запросы сейчас',
          bestByRpm
            ? `Сейчас самый свободный по остаткам RPM провайдер — ${bestByRpm.provider}. Осталось примерно ${fmt(bestByRpm.rpmRemaining)} RPM.`
            : 'Недостаточно данных по RPM.'
        ),
        recommendationCard(
          'Где ресурс заканчивается быстрее всего',
          lowestByRpm
            ? `Ближе всего к исчерпанию сейчас ${lowestByRpm.provider}. Остаток RPM: ${fmt(lowestByRpm.rpmRemaining)}.`
            : 'Недостаточно данных по RPM.'
        ),
        recommendationCard(
          'Кто лучше для тяжёлых запросов',
          bestByTokens
            ? `Если запросы крупные по токенам, сейчас логичнее смотреть на ${bestByTokens.provider}. Осталось токенов в минуту: ${fmt(bestByTokens.tpmRemaining)}.`
            : 'Провайдеры не отдали счётчики токенов в минуту.'
        ),
        recommendationCard(
          'Где сейчас больше всего пригодных моделей',
          modelCounts[0]
            ? `Больше всего моделей со статусом OK и live-лимитами сейчас у провайдера ${modelCounts[0].provider}: ${modelCounts[0].count}.`
            : 'Нет данных по моделям.'
        ),
      ].join('');
    }

    function groupSection(title, subtitle, rowsHtml) {
      return `
        <section>
          <h2 class="group-title">${title}</h2>
          <p class="group-sub">${subtitle}</p>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Провайдер</th>
                  <th>Модель</th>
                  <th>Осталось RPM</th>
                  <th>Осталось RPD</th>
                  <th>Осталось токенов/мин</th>
                  <th class="hidden-meta">Макс</th>
                  <th>Источник</th>
                  <th>Статус</th>
                  <th>Последнее наблюдение</th>
                  <th>Проверка</th>
                </tr>
              </thead>
              <tbody>${rowsHtml || `<tr><td colspan="10" class="empty">В этой группе моделей нет</td></tr>`}</tbody>
            </table>
          </div>
        </section>
      `;
    }

    function validatedGroupSection(rowsHtml, meta) {
      return `
        <section>
          <h2 class="group-title">Проверенные модели LLM</h2>
          <p class="group-sub">LLM-модели вне Блока №2, которые прошли отдельную текстовую проверку. Последняя проверка: ${fmt(formatGmtPlus5(meta?.validated_at))}. Данные загружены из кэша. Кэш обновлён: ${fmt(formatGmtPlus5(meta?.cache_created_at))}.</p>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Провайдер</th>
                  <th>Модель</th>
                  <th>Ответ на тест</th>
                  <th>Последняя проверка</th>
                  <th>Проверка</th>
                </tr>
              </thead>
              <tbody>${rowsHtml || `<tr><td colspan="5" class="empty">Пока нет отдельно проверенных LLM-моделей</td></tr>`}</tbody>
            </table>
          </div>
        </section>
      `;
    }

    function renderValidatedLlmProgress(job) {
      const total = Number(job?.total_models || 0);
      const requestsStarted = Number(job?.requests_started || 0);
      const responsesReceived = Number(job?.responses_received || 0);
      const requestsPercent = percent(requestsStarted, total);
      const responsesPercent = percent(responsesReceived, total);

      if (!job?.running && !job?.last_started_at) {
        validatedLlmState.style.display = 'none';
        validatedLlmState.innerHTML = '';
        return;
      }

      validatedLlmState.style.display = 'block';
      validatedLlmState.innerHTML = `
        <div>Идет проверка оставшихся LLM-моделей. Подождите...</div>
        <div class="progress-stack">
          <div class="progress-line">
            <div class="progress-meta">
              <span>Запросы на тестирование</span>
              <span>${requestsStarted} / ${total} (${requestsPercent}%)</span>
            </div>
            <div class="progress-track"><div class="progress-fill" style="width:${requestsPercent}%"></div></div>
          </div>
          <div class="progress-line">
            <div class="progress-meta">
              <span>Полученные ответы</span>
              <span>${responsesReceived} / ${total} (${responsesPercent}%)</span>
            </div>
            <div class="progress-track"><div class="progress-fill" style="width:${responsesPercent}%"></div></div>
          </div>
          <div class="sub">Статус: ${fmt(job?.status)}. Успешно: ${fmt(job?.passed)}. Не прошло: ${fmt(job?.failed)}.</div>
        </div>
      `;
    }

    async function getValidatedLlmJobStatus() {
      return getJson('/admin/models/validate-remaining-llm/status');
    }

    async function syncValidatedLlmJobStatus({ reloadOnFinish = false } = {}) {
      try {
        const job = await getValidatedLlmJobStatus();
        renderValidatedLlmProgress(job);
        if (!job.running && validatedLlmProgressHandle) {
          clearInterval(validatedLlmProgressHandle);
          validatedLlmProgressHandle = null;
          if (reloadOnFinish) {
            await loadDashboard();
          }
        }
        return job;
      } catch (error) {
        validatedLlmState.style.display = 'block';
        validatedLlmState.innerHTML = `<div class="status-error">${error.message}</div>`;
        throw error;
      }
    }

    function startValidatedLlmProgressPolling() {
      if (validatedLlmProgressHandle) {
        clearInterval(validatedLlmProgressHandle);
      }
      validatedLlmProgressHandle = setInterval(() => {
        syncValidatedLlmJobStatus({ reloadOnFinish: true });
      }, 3000);
    }

    async function loadValidatedLlmBlock() {
      try {
        const [payload, job] = await Promise.all([
          getJson('/admin/models/validated-llm'),
          getValidatedLlmJobStatus()
        ]);
        const rows = (payload.data || []).map((model) => validatedRowHtml(model)).join('');
        validatedLlmNode.innerHTML = validatedGroupSection(rows, payload.meta || {});
        renderValidatedLlmProgress(job);
        if (job?.running) {
          startValidatedLlmProgressPolling();
        } else if ((!payload.data || payload.data.length === 0) && !job?.running && !job?.last_started_at) {
          await refreshValidatedLlm('auto');
          return;
        }
        wireProviderTests();
      } catch (error) {
        validatedLlmNode.innerHTML = `<div class="status-error">${error.message}</div>`;
      }
    }

    async function getJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      return response.json();
    }

    async function loadDashboard() {
      loadingState.style.display = 'block';
      groupedTables.innerHTML = '';
      recommendationsNode.innerHTML = recommendationCard('Идет анализ', 'Собираем live-счетчики и готовим рекомендации...');
      validatedLlmNode.innerHTML = '';
      try {
        const [health, models, estimates] = await Promise.all([
          getJson('/health/limits'),
          getJson('/admin/models/available'),
          getJson('/admin/limits/estimated')
        ]);
        const previousTrendState = getTrendState();
        const nextTrendState = {};

        overviewStats.innerHTML = [
          statCard('Сервис', health.status),
          statCard('Провайдеры', health.providers_count),
          statCard('Модели', (models.data || []).length, `после фильтра из: ${fmt(models.meta?.total_before_filter)}`),
          statCard('Последний probe', formatGmtPlus5(health.startup_probe?.last_probe_at), `успешно: ${fmt(health.startup_probe?.summary?.successful?.length || 0)}`)
        ].join('');

        const grouped = {
          llm: [],
          audio: [],
          video: [],
          other: [],
        };

        const preparedRows = [];

        (models.data || []).forEach((model) => {
          const liveItem = (health.limits || {})[model.provider] || {};
          const estimate = (estimates.providers || {})[model.provider] || {};
          if (!isOkStatus(liveItem, estimate)) {
            return;
          }
          const category = categoryForModel(model);
          const key = trendKey(model);
          const previous = previousTrendState[key] || {};
          const currentRpm = numericOrNull(observedRpm(liveItem));
          const currentRpd = numericOrNull(observedRpd(liveItem));
          let direction = previous.direction || '';
          let highlightClass = '';

          if (currentRpm !== null && previous.rpm !== null && previous.rpm !== undefined && currentRpm !== previous.rpm) {
            if (currentRpm > previous.rpm) {
              direction = 'up';
              highlightClass = 'trend-up';
            } else {
              direction = 'down';
              highlightClass = 'trend-down';
            }
          } else if (currentRpm === null && currentRpd !== null && previous.rpd !== null && previous.rpd !== undefined && currentRpd !== previous.rpd) {
            if (currentRpd > previous.rpd) {
              direction = 'up';
              highlightClass = 'trend-up';
            } else {
              direction = 'down';
              highlightClass = 'trend-down';
            }
          }

          nextTrendState[key] = {
            rpm: currentRpm,
            rpd: currentRpd,
            direction,
          };

          preparedRows.push({
            category,
            model,
            liveItem,
            estimate,
            trendInfo: { direction, highlightClass },
            weight: resourceWeight(model, liveItem),
          });
        });
        preparedRows.sort(compareModelsByPriority);
        preparedRows.forEach((item) => {
          grouped[item.category].push(rowHtml(item.model, item.liveItem, item.estimate, item.trendInfo));
        });
        setTrendState(nextTrendState);

        groupedTables.innerHTML = [
          groupSection('LLM модели', 'Все языковые модели всех поставщиков.', grouped.llm.join('')),
          groupSection('Аудио распознавание', 'Модели распознавания речи и транскрибации.', grouped.audio.join('')),
          groupSection('Видео модели', 'Видео-модели и связанные генеративные видео сервисы.', grouped.video.join('')),
          groupSection('Остальные модели', 'Все остальные модели, которые не попали в первые три группы.', grouped.other.join('')),
        ].join('');
        recommendationsNode.innerHTML = buildRecommendations(health, models);
        await loadValidatedLlmBlock();
        loadingState.style.display = 'none';

        wireProviderTests();
      } catch (error) {
        overviewStats.innerHTML = [
          statCard('Сервис', 'failed'),
          statCard('Ошибка', error.message)
        ].join('');
        groupedTables.innerHTML = `<div class="status-error">${error.message}</div>`;
        recommendationsNode.innerHTML = recommendationCard('Ошибка анализа', error.message);
        validatedLlmNode.innerHTML = `<div class="status-error">${error.message}</div>`;
        loadingState.style.display = 'none';
      }
    }

    async function refreshLive() {
      await getJson('/health/limits/live', { method: 'POST' });
      await loadDashboard();
    }

    async function refreshValidatedLlm(startedBy = 'manual') {
      const payload = await getJson(`/admin/models/validate-remaining-llm?started_by=${encodeURIComponent(startedBy)}`, { method: 'POST' });
      renderValidatedLlmProgress(payload.job || payload);
      startValidatedLlmProgressPolling();
    }

    function resultNodeId(provider, model) {
      return `test-result-${provider}-${String(model).replace(/[^a-zA-Z0-9_-]/g, '_')}`;
    }

    async function testProvider(provider, model) {
      const resultNode = document.getElementById(resultNodeId(provider, model));
      if (resultNode) resultNode.textContent = 'проверка...';
      try {
        const url = `/admin/test?provider_name=${encodeURIComponent(provider)}&model_id=${encodeURIComponent(model)}`;
        const payload = await getJson(url, { method: 'POST' });
        if (resultNode) resultNode.textContent = `${payload.model}: ${payload.message_excerpt || 'ok'}`;
      } catch (error) {
        if (resultNode) resultNode.textContent = error.message;
      }
    }

    function wireProviderTests() {
      document.querySelectorAll('[data-provider]').forEach((button) => {
        const provider = button.dataset.provider;
        const model = button.dataset.model;
        button.onclick = () => testProvider(provider, model);
      });
    }

    function startAutoRefresh() {
      if (autoRefreshHandle) clearInterval(autoRefreshHandle);
      const minutes = Number(refreshInterval.value || 3);
      autoRefreshHandle = setInterval(loadDashboard, minutes * 60 * 1000);
    }

    document.getElementById('refreshAll').addEventListener('click', loadDashboard);
    document.getElementById('refreshLive').addEventListener('click', refreshLive);
    document.getElementById('refreshValidatedLlm').addEventListener('click', refreshValidatedLlm);
    refreshInterval.addEventListener('change', startAutoRefresh);
    loadDashboard();
    startAutoRefresh();
  </script>
</body>
</html>
"""


def _load_estimated_limits() -> dict:
    if not LIMITS_FILE.exists():
        return {"snapshot_date": None, "providers": {}}
    return json.loads(LIMITS_FILE.read_text(encoding="utf-8"))


def _load_model_validation_results() -> dict:
    if not MODEL_VALIDATION_FILE.exists():
        return {"validated_at": None, "models": {}}
    try:
        return json.loads(MODEL_VALIDATION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"validated_at": None, "models": {}}


def _save_model_validation_results(payload: dict) -> None:
    MODEL_VALIDATION_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_admin_cache() -> dict:
    if not ADMIN_CACHE_FILE.exists():
        return {"validated_llm": {"object": "list", "data": [], "meta": {"cache_created_at": None}}}
    try:
        return json.loads(ADMIN_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"validated_llm": {"object": "list", "data": [], "meta": {"cache_created_at": None}}}


def _save_admin_cache(payload: dict) -> None:
    ADMIN_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _get_validated_llm_job_state() -> dict:
    return dict(VALIDATED_LLM_JOB_STATE)


def _reset_validated_llm_job_state(started_by: str | None = None) -> None:
    VALIDATED_LLM_JOB_STATE.update(
        {
            "status": "running",
            "running": True,
            "requests_started": 0,
            "responses_received": 0,
            "total_models": 0,
            "passed": 0,
            "failed": 0,
            "started_by": started_by,
            "last_started_at": datetime.now(timezone.utc).isoformat(),
            "last_finished_at": None,
            "error": None,
        }
    )


def _provider_recommendation(provider_state: dict) -> str:
    if provider_state.get("last_error"):
        return "retry"
    limits = provider_state.get("limits", {})
    requests_minute = limits.get("requests", {}).get("minute", {})
    requests_day = limits.get("requests", {}).get("day", {})
    rpm_remaining = requests_minute.get("remaining")
    rpd_remaining = requests_day.get("remaining")
    source = limits.get("source")

    if rpm_remaining == 0 or rpd_remaining == 0:
        return "wait"
    if source == "fallback_default":
        return "wait"
    return "ready"


def _model_validity(model: dict, validation_payload: dict) -> bool | None:
    if _category_for_model(model) != "llm":
        return None
    key = _model_validation_key(model.get("provider", ""), model.get("id", ""))
    item = validation_payload.get("models", {}).get(key, {})
    if "passed" not in item:
        return None
    return item.get("passed") is True


def _build_dispatcher_cache_payload(
    all_models: list[dict] | None = None,
    block_two_payload: dict | None = None,
    validated_llm_payload: dict | None = None,
) -> dict:
    provider_names = list(settings.get_provider_configs().keys())
    limits_snapshot = rate_limit_store.get_snapshot(provider_names)
    estimated_limits = _load_estimated_limits().get("providers", {})
    validation_payload = _load_model_validation_results()
    cache = _load_admin_cache()

    if block_two_payload is None:
        block_two_payload = cache.get("block_two", {"object": "list", "data": [], "meta": {}})
    if validated_llm_payload is None:
        validated_llm_payload = cache.get("validated_llm", {"object": "list", "data": [], "meta": {}})

    routes = cache.get("routes", [])
    if all_models is not None:
        routes = []
        for model in all_models:
            provider_name = model.get("provider")
            provider_state = limits_snapshot.get(provider_name, {})
            validity = _model_validity(model, validation_payload)
            routes.append(
                {
                    "provider": provider_name,
                    "model_id": model.get("id"),
                    "category": _category_for_model(model),
                    "valid": validity,
                    "last_status_code": provider_state.get("last_status_code"),
                    "last_error": provider_state.get("last_error"),
                    "last_observed_at": provider_state.get("last_observed_at"),
                    "rpm_remaining": provider_state.get("limits", {}).get("requests", {}).get("minute", {}).get("remaining"),
                    "rpd_remaining": provider_state.get("limits", {}).get("requests", {}).get("day", {}).get("remaining"),
                    "tpm_remaining": provider_state.get("limits", {}).get("tokens", {}).get("minute", {}).get("remaining"),
                    "validity_source": "llm_text_test" if _category_for_model(model) == "llm" else "not_required",
                    "recommendation": _provider_recommendation(provider_state),
                }
            )

    providers = []
    for provider_name in provider_names:
        provider_state = limits_snapshot.get(provider_name, {})
        providers.append(
            {
                "provider": provider_name,
                "valid": provider_state.get("last_error") in (None, ""),
                "last_status_code": provider_state.get("last_status_code"),
                "last_error": provider_state.get("last_error"),
                "last_observed_at": provider_state.get("last_observed_at"),
                "limits": provider_state.get("limits", {}),
                "estimated_limits": estimated_limits.get(provider_name, {}),
                "recommendation": _provider_recommendation(provider_state),
            }
        )

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "providers": providers,
        "routes": routes,
        "block_two": block_two_payload,
        "validated_llm": validated_llm_payload,
    }


def _refresh_admin_cache(
    all_models: list[dict] | None = None,
    block_two_payload: dict | None = None,
    validated_llm_payload: dict | None = None,
) -> dict:
    cache_payload = _load_admin_cache()
    dispatcher_payload = _build_dispatcher_cache_payload(
        all_models=all_models,
        block_two_payload=block_two_payload,
        validated_llm_payload=validated_llm_payload,
    )
    cache_payload.update(dispatcher_payload)
    _save_admin_cache(cache_payload)
    return cache_payload


def _normalize_test_reply(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.lower().replace("ё", "е")
    return "".join(ch for ch in lowered if ch.isalnum() or ch.isspace()).strip()


def _normalize_test_reply(value: str | None) -> str:
    if not value:
        return ""
    lowered = (
        value.lower()
        .replace("ё", "е")
        .replace("-", " ")
        .replace("уа ", "ва ")
    )
    return "".join(ch for ch in lowered if ch.isalnum() or ch.isspace()).strip()


def _is_valid_test_reply(value: str | None) -> bool:
    normalized = _normalize_test_reply(value)
    if not normalized:
        return False
    return any(expected in normalized for expected in EXPECTED_TEST_REPLIES)


def _live_limit_models(models: list[dict]) -> list[dict]:
    return _filter_models_by_validation(_filter_models_with_live_limits(models))


def _block_two_model_keys(models: list[dict]) -> set[str]:
    return {
        _model_validation_key(model.get("provider", ""), model.get("id", ""))
        for model in models
        if isinstance(model, dict) and model.get("provider") and model.get("id")
    }


def _remaining_llm_models(all_models: list[dict]) -> list[dict]:
    current_plan_models = _filter_models_for_current_plan(all_models)
    block_two_models = _live_limit_models(current_plan_models)
    excluded_keys = _block_two_model_keys(block_two_models)
    return [
        model
        for model in current_plan_models
        if _category_for_model(model) == "llm"
        and _model_validation_key(model.get("provider", ""), model.get("id", "")) not in excluded_keys
    ]


def _remaining_llm_models_from_keys(all_models: list[dict], excluded_keys: set[str]) -> list[dict]:
    current_plan_models = _filter_models_for_current_plan(all_models)
    return [
        model
        for model in current_plan_models
        if _category_for_model(model) == "llm"
        and _model_validation_key(model.get("provider", ""), model.get("id", "")) not in excluded_keys
    ]


def _merge_validation_results(existing_payload: dict, new_results: dict, validated_at: str) -> dict:
    merged = dict(existing_payload or {})
    merged_models = dict((existing_payload or {}).get("models", {}))
    merged_models.update(new_results)
    merged["validated_at"] = validated_at
    merged["models"] = merged_models
    return merged


def _build_validated_llm_cache_payload(
    remaining_models: list[dict],
    validation_payload: dict,
) -> dict:
    validation_models = validation_payload.get("models", {})
    passed_models = []

    for model in remaining_models:
        key = _model_validation_key(model.get("provider", ""), model.get("id", ""))
        validation_item = validation_models.get(key, {})
        if validation_item.get("passed") is True:
            enriched = dict(model)
            enriched["_validation"] = {
                "message_excerpt": validation_item.get("message_excerpt"),
                "error": validation_item.get("error"),
                "validated_at": validation_payload.get("validated_at"),
            }
            passed_models.append(enriched)

    return {
        "object": "list",
        "data": passed_models,
        "meta": {
            "filter": "remaining_llm_passed_validation",
            "validated_at": validation_payload.get("validated_at"),
            "total_candidates": len(remaining_models),
            "total_after_filter": len(passed_models),
            "cache_created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


async def _execute_model_test(provider_name: str, model_id: str) -> tuple[bool | None, str | None, str | None]:
    request = ChatCompletionRequest(
        provider=provider_name,
        model=model_id,
        messages=[{"role": "user", "content": TEST_PROMPT}],
        max_tokens=32,
        temperature=0.1,
    )

    try:
        response = await provider_router.race_chat_completion(request)
        choices = response.get("choices", [])
        message_excerpt = None
        if choices and isinstance(choices[0], dict):
            message_excerpt = ((choices[0].get("message") or {}).get("content") or "")[:300]
        return _is_valid_test_reply(message_excerpt), message_excerpt, None
    except Exception as exc:
        return False, None, str(exc)


def _store_model_test_result(
    provider_name: str,
    model_id: str,
    passed_validation: bool | None,
    message_excerpt: str | None,
    error_text: str | None,
) -> dict:
    validation_payload = _load_model_validation_results()
    validation_payload["validated_at"] = datetime.now(timezone.utc).isoformat()
    validation_payload.setdefault("models", {})[_model_validation_key(provider_name, model_id)] = {
        "provider": provider_name,
        "model_id": model_id,
        "passed": passed_validation,
        "message_excerpt": message_excerpt,
        "error": error_text,
        "tested_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_model_validation_results(validation_payload)
    return validation_payload


async def _validate_llm_models(candidate_models: list[dict], merge_existing: bool = False) -> dict:
    validation_payload = _load_model_validation_results() if merge_existing else {"validated_at": None, "models": {}}
    new_results: dict[str, dict] = {}
    passed = 0
    failed = 0

    for model in candidate_models:
        provider_name = model.get("provider")
        model_id = model.get("id")
        if not provider_name or not model_id:
            continue

        passed_validation, message_excerpt, error_text = await _execute_model_test(provider_name, model_id)

        new_results[_model_validation_key(provider_name, model_id)] = {
            "provider": provider_name,
            "model_id": model_id,
            "passed": passed_validation,
            "message_excerpt": message_excerpt,
            "error": error_text,
        }

        validation_payload = _merge_validation_results(
            validation_payload,
            {_model_validation_key(provider_name, model_id): new_results[_model_validation_key(provider_name, model_id)]},
            datetime.now(timezone.utc).isoformat(),
        )
        _save_model_validation_results(validation_payload)

        if passed_validation:
            passed += 1
        else:
            failed += 1

    return {
        "status": "ok",
        "validated": len(candidate_models),
        "passed": passed,
        "failed": failed,
        "validated_at": validation_payload.get("validated_at"),
    }


async def _run_validated_llm_job(started_by: str) -> None:
    global VALIDATED_LLM_JOB_TASK

    _reset_validated_llm_job_state(started_by)
    try:
        models_payload = await provider_router.get_models()
        all_models = models_payload.get("data", [])
        block_two_payload = await get_available_models_for_admin()
        excluded_keys = _block_two_model_keys(block_two_payload.get("data", []))
        remaining_models = _remaining_llm_models_from_keys(all_models, excluded_keys)

        VALIDATED_LLM_JOB_STATE["total_models"] = len(remaining_models)
        passed = 0
        failed = 0

        for index, model in enumerate(remaining_models, start=1):
            provider_name = model.get("provider")
            model_id = model.get("id")
            if not provider_name or not model_id:
                continue

            VALIDATED_LLM_JOB_STATE["requests_started"] = index
            passed_validation, message_excerpt, error_text = await _execute_model_test(provider_name, model_id)
            _store_model_test_result(provider_name, model_id, passed_validation, message_excerpt, error_text)
            VALIDATED_LLM_JOB_STATE["responses_received"] += 1

            if passed_validation:
                passed += 1
            else:
                failed += 1

            VALIDATED_LLM_JOB_STATE["passed"] = passed
            VALIDATED_LLM_JOB_STATE["failed"] = failed

        validation_payload = _load_model_validation_results()
        validated_llm_payload = _build_validated_llm_cache_payload(remaining_models, validation_payload)
        _refresh_admin_cache(
            all_models=all_models,
            block_two_payload=block_two_payload,
            validated_llm_payload=validated_llm_payload,
        )
        VALIDATED_LLM_JOB_STATE["status"] = "completed"
    except Exception as exc:
        VALIDATED_LLM_JOB_STATE["status"] = "failed"
        VALIDATED_LLM_JOB_STATE["error"] = str(exc)
    finally:
        VALIDATED_LLM_JOB_STATE["running"] = False
        VALIDATED_LLM_JOB_STATE["last_finished_at"] = datetime.now(timezone.utc).isoformat()
        VALIDATED_LLM_JOB_TASK = None


def _model_validation_key(provider: str, model_id: str) -> str:
    return f"{provider}::{model_id}"


def _category_for_model(model: dict) -> str:
    model_id = str(model.get("id", "")).lower()
    name = str(model.get("name", "")).lower()
    description = str(model.get("description", "")).lower()
    haystack = f"{model_id} {name} {description}"

    audio_hints = ["whisper", "transcribe", "transcription", "speech-to-text", "stt", "asr", "audio"]
    video_hints = ["video", "veo", "sora", "movie", "clip", "vision-video", "gen-video"]
    llm_hints = [
        "chat",
        "instruct",
        "llama",
        "gpt",
        "gemini",
        "qwen",
        "deepseek",
        "claude",
        "mistral",
        "command",
        "language",
        "reason",
        "completion",
    ]

    if any(hint in haystack for hint in audio_hints):
        return "audio"
    if any(hint in haystack for hint in video_hints):
        return "video"
    if any(hint in haystack for hint in llm_hints):
        return "llm"
    return "other"


def _select_test_model(provider_name: str, models: list[dict]) -> str | None:
    model_ids = [item.get("id") for item in models if isinstance(item, dict) and item.get("id")]
    for preferred in PREFERRED_TEST_MODELS.get(provider_name, []):
        if preferred in model_ids:
            return preferred
    return model_ids[0] if model_ids else None


def _is_model_available_for_current_plan(model: dict) -> bool:
    provider = model.get("provider")
    model_id = str(model.get("id", "")).lower()

    if provider == "openrouter":
        return model_id.endswith(":free")

    if provider == "gemini":
        return any(model_id.startswith(prefix) for prefix in GEMINI_FREE_TIER_PREFIXES)

    if provider == "groq":
        if not model.get("active", True):
            return False
        return not any(model_id.startswith(prefix) for prefix in GROQ_EXCLUDED_PREFIXES)

    if provider in {"cerebras", "sambanova"}:
        return True

    return True


def _filter_models_for_current_plan(models: list[dict]) -> list[dict]:
    return [
        model
        for model in models
        if isinstance(model, dict) and model.get("id") and _is_model_available_for_current_plan(model)
    ]


def _filter_models_with_live_limits(models: list[dict]) -> list[dict]:
    snapshot = rate_limit_store.get_snapshot(list(settings.get_provider_configs().keys()))
    providers_with_live_limits = {
        provider
        for provider, item in snapshot.items()
        if item.get("limits", {}).get("source") == "response_headers"
    }
    return [
        model
        for model in models
        if isinstance(model, dict) and model.get("provider") in providers_with_live_limits
    ]


def _filter_models_by_validation(models: list[dict]) -> list[dict]:
    validation_payload = _load_model_validation_results()
    validated_models = validation_payload.get("models", {})
    passed_keys = {
        key
        for key, item in validated_models.items()
        if isinstance(item, dict) and item.get("passed") is True
    }
    if not passed_keys:
        return models
    return [
        model
        for model in models
        if _category_for_model(model) != "llm"
        or _model_validation_key(model.get("provider", ""), model.get("id", "")) in passed_keys
    ]


def _remaining_rpm(item: dict) -> int | None:
    return item.get("limits", {}).get("requests", {}).get("minute", {}).get("remaining")


def _remaining_rpd(item: dict) -> int | None:
    return item.get("limits", {}).get("requests", {}).get("day", {}).get("remaining")


def _remaining_tpm(item: dict) -> int | None:
    return item.get("limits", {}).get("tokens", {}).get("minute", {}).get("remaining")


def _pick_auto_provider(chat_models: list[dict]) -> str | None:
    provider_names = list(settings.get_provider_configs().keys())
    snapshot = rate_limit_store.get_snapshot(provider_names)
    provider_candidates: list[dict] = []

    for provider_name, item in snapshot.items():
        if item.get("limits", {}).get("source") != "response_headers":
            continue

        valid_models = [
            model
            for model in chat_models
            if model.get("provider") == provider_name and _category_for_model(model) == "llm"
        ]
        if not valid_models:
            continue

        provider_candidates.append(
            {
                "provider": provider_name,
                "rpm_remaining": _remaining_rpm(item) or -1,
                "rpd_remaining": _remaining_rpd(item) or -1,
                "tpm_remaining": _remaining_tpm(item) or -1,
                "models_count": len(valid_models),
            }
        )

    if not provider_candidates:
        return None

    provider_candidates.sort(
        key=lambda item: (
            item["rpm_remaining"],
            item["tpm_remaining"],
            item["rpd_remaining"],
            item["models_count"],
        ),
        reverse=True,
    )
    return provider_candidates[0]["provider"]


async def _sample_provider_limits() -> None:
    for provider_name in provider_router.list_available_providers():
        try:
            models_payload = await provider_router.get_models(provider_name)
        except (ValueError, UpstreamProvidersExhausted):
            continue

        models = models_payload.get("data", [])
        selected_model = _select_test_model(provider_name, models)
        if not selected_model:
            continue

        request = ChatCompletionRequest(
            provider=provider_name,
            model=selected_model,
            messages=[{"role": "user", "content": TEST_PROMPT}],
            max_tokens=32,
            temperature=0.1,
        )
        try:
            await provider_router.race_chat_completion(request)
        except (ValueError, UpstreamProvidersExhausted):
            continue


@router.get("/health/limits", tags=["Health"])
async def get_limits_health() -> dict:
    provider_names = list(settings.get_provider_configs().keys())
    return {
        "status": "ok",
        "providers": provider_names,
        **rate_limit_store.get_health_payload(provider_names),
    }


@router.get("/admin", response_class=HTMLResponse, tags=["Admin"])
async def admin_dashboard() -> HTMLResponse:
    return HTMLResponse(content=ADMIN_PAGE_HTML)


@router.get("/admin/limits/estimated", tags=["Admin"])
async def get_estimated_limits() -> dict:
    return _load_estimated_limits()


@router.get("/admin/dispatcher/cache", tags=["Admin"])
async def get_dispatcher_cache() -> dict:
    return _load_admin_cache()


@router.get("/admin/models/available", tags=["Admin"])
async def get_available_models_for_admin() -> dict:
    try:
        models_payload = await provider_router.get_models()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)

    all_models = models_payload.get("data", [])
    filtered_models = _filter_models_for_current_plan(all_models)
    filtered_models = _filter_models_with_live_limits(filtered_models)
    filtered_models = _filter_models_by_validation(filtered_models)
    payload = {
        "object": "list",
        "data": filtered_models,
        "meta": {
            "filter": "current_plan_only_and_live_limits_only",
            "total_before_filter": len(all_models),
            "total_after_filter": len(filtered_models),
        },
    }
    _refresh_admin_cache(all_models=all_models, block_two_payload=payload)
    return payload


@router.get("/admin/models/validated-llm", tags=["Admin"])
async def get_validated_llm_models_for_admin() -> dict:
    cache_payload = _load_admin_cache()
    validated_llm = cache_payload.get("validated_llm")
    if isinstance(validated_llm, dict):
        return validated_llm
    return {"object": "list", "data": [], "meta": {"cache_created_at": None}}


@router.get("/admin/models/validate-remaining-llm/status", tags=["Admin"])
async def get_validate_remaining_llm_status() -> dict:
    return _get_validated_llm_job_state()


@router.post("/admin/models/validate-all", tags=["Admin"])
async def validate_all_models_for_admin() -> dict:
    try:
        models_payload = await provider_router.get_models()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)

    all_models = models_payload.get("data", [])
    candidate_models = _filter_models_for_current_plan(all_models)
    candidate_models = _filter_models_with_live_limits(candidate_models)
    candidate_models = [model for model in candidate_models if _category_for_model(model) == "llm"]

    result = await _validate_llm_models(candidate_models, merge_existing=True)
    block_two_payload = await get_available_models_for_admin()
    _refresh_admin_cache(all_models=all_models, block_two_payload=block_two_payload)
    return result


@router.post("/admin/models/validate-remaining-llm", tags=["Admin"])
async def validate_remaining_llm_models_for_admin(started_by: str = Query(default="manual")) -> dict:
    global VALIDATED_LLM_JOB_TASK

    if VALIDATED_LLM_JOB_TASK and not VALIDATED_LLM_JOB_TASK.done():
        return {"status": "running", "job": _get_validated_llm_job_state()}

    _reset_validated_llm_job_state(started_by)
    VALIDATED_LLM_JOB_TASK = asyncio.create_task(_run_validated_llm_job(started_by))
    return {"status": "started", "job": _get_validated_llm_job_state()}


@router.post("/admin/test", tags=["Admin"])
async def test_provider(
    provider_name: str = Query(...),
    model_id: str | None = Query(default=None),
) -> dict:
    try:
        models_payload = await provider_router.get_models(provider_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)

    models = models_payload.get("data", [])
    available_ids = [item.get("id") for item in models if isinstance(item, dict) and item.get("id")]
    selected_model = model_id if model_id in available_ids else _select_test_model(provider_name, models)
    if not selected_model:
        raise HTTPException(status_code=404, detail=f"No models available for provider '{provider_name}'")

    request = ChatCompletionRequest(
        provider=provider_name,
        model=selected_model,
        messages=[{"role": "user", "content": TEST_PROMPT}],
        max_tokens=32,
        temperature=0.1,
    )

    try:
        response = await provider_router.race_chat_completion(request)
    except ValueError as exc:
        _store_model_test_result(provider_name, selected_model, None, None, str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        _store_model_test_result(provider_name, selected_model, None, None, str(exc))
        raise HTTPException(status_code=502, detail=exc.errors)

    message = None
    choices = response.get("choices", [])
    if choices and isinstance(choices[0], dict):
        message = (choices[0].get("message") or {}).get("content")

    passed_validation = None
    if any(
        item.get("id") == selected_model and _category_for_model(item) == "llm"
        for item in models
        if isinstance(item, dict)
    ):
        passed_validation = _is_valid_test_reply(message)
    _store_model_test_result(
        provider_name,
        selected_model,
        passed_validation,
        message[:300] if isinstance(message, str) else None,
        None,
    )
    _refresh_admin_cache()

    return {
        "provider": provider_name,
        "model": selected_model,
        "selected_provider": response.get("_proxy", {}).get("selected_provider"),
        "message_excerpt": message[:300] if isinstance(message, str) else None,
    }


@router.post("/health/limits/live", tags=["Health"])
async def refresh_limits_health() -> dict:
    provider_names = list(settings.get_provider_configs().keys())
    try:
        probe_summary = await provider_router.probe_provider_limits()
        rate_limit_store.record_probe_summary(
            successful=probe_summary["successful"],
            failed=probe_summary["failed"],
        )
        await _sample_provider_limits()
        await validate_all_models_for_admin()
        _refresh_admin_cache()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "status": "ok",
        "providers": provider_names,
        **rate_limit_store.get_health_payload(provider_names),
    }


@router.get("/v1/models", tags=["Models"])
async def get_models() -> dict:
    try:
        return await provider_router.get_models()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)


@router.post("/v1/chat/completions", tags=["Chat"])
async def create_chat_completion(request: ChatCompletionRequest) -> dict:
    effective_request = request

    if request.provider == "auto":
        models_payload = await provider_router.get_models()
        candidate_models = _filter_models_for_current_plan(models_payload.get("data", []))
        candidate_models = _filter_models_with_live_limits(candidate_models)
        candidate_models = _filter_models_by_validation(candidate_models)
        auto_provider = _pick_auto_provider(candidate_models)
        effective_request = request.model_copy(update={"provider": auto_provider})

    try:
        response = await provider_router.race_chat_completion(effective_request)
        response.setdefault("_proxy", {})
        if request.provider == "auto":
            response["_proxy"]["requested_provider"] = "auto"
            response["_proxy"]["auto_selected_provider"] = effective_request.provider
            response["_proxy"]["selected_policy"] = (
                "recommendations" if effective_request.provider else "fastest_fallback"
            )
        _refresh_admin_cache()
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)


@router.post("/v1/embeddings", tags=["Embeddings"])
async def create_embeddings(request: EmbeddingRequest) -> dict:
    try:
        return await provider_router.race_embeddings(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)
