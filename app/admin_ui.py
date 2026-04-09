ADMIN_PAGE_HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AshybulakStroy AI HUB Admin</title>
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
    .danger-text {
      color: var(--bad);
      font-weight: 700;
      display: block;
      margin-top: 6px;
      font-size: 14px;
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
    tr.error td { background: rgba(248, 113, 113, 0.10); }
    tr.invalid-resource-row td { background: rgba(248, 113, 113, 0.08); }
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
      <h1>AshybulakStroy AI HUB</h1>
      <p class="lead">Одна таблица сверху вниз: каждая строка это модель, а лимиты подтягиваются из live-наблюдений провайдера и сохранённой оценки RPM/RPD.</p>
      <div class="actions">
        <button id="refreshAll">Обновить</button>
        <button id="refreshLive" class="secondary">Обновить live-лимиты</button>
        <label class="refresh-control">
          <span>Режим прокси</span>
          <select id="proxyModeSelect">
            <option value="LOAD_BALANCE">LOAD_BALANCE</option>
            <option value="FAST">FAST</option>
          </select>
        </label>
        <button id="applyProxyMode" class="secondary">Применить режим</button>
        <label class="refresh-control">
          <span>Язык</span>
          <select id="languageSelect">
            <option value="ru">СНГ / Русский</option>
            <option value="kz">Азия / Қазақша</option>
            <option value="ar">العربية</option>
            <option value="en-gb">Europe / English</option>
            <option value="en-us">America / English</option>
            <option value="zh-cn">China / 中文</option>
          </select>
        </label>
        <label class="refresh-control">
          <span>Автообновление</span>
          <select id="refreshInterval">
            <option value="1">1 мин</option>
            <option value="3">3 мин</option>
            <option value="5">5 мин</option>
            <option value="10" selected>10 мин</option>
            <option value="20">20 мин</option>
            <option value="40">40 мин</option>
            <option value="60">1 час</option>
          </select>
        </label>
      </div>
    </section>

    <section class="panel">
      <div class="label">Блок №1</div>
      <div class="stats" id="overviewStats"></div>
    </section>

    <section class="panel">
      <div class="label">Блок №1.5</div>
      <div class="label">Активные прокси-сессии</div>
      <div id="activeProxySessions" class="table-wrap"><div class="empty">Нет активных прокси-сессий</div></div>
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

    <section class="panel">
      <div class="label">Блок №5</div>
      <div class="label">История прокси-сессий</div>
      <div id="proxySessionHistory" class="table-wrap"><div class="empty">Пока нет завершённых сессий</div></div>
    </section>

    <section class="panel">
      <div class="label">Блок №6</div>
      <div class="label">Invalid resources</div>
      <div id="invalidResources" class="table-wrap"><div class="empty">Список invalid resources пока пуст</div></div>
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
    const proxyModeSelect = document.getElementById('proxyModeSelect');
    const applyProxyModeButton = document.getElementById('applyProxyMode');
    const activeProxySessionsNode = document.getElementById('activeProxySessions');
    const proxySessionHistoryNode = document.getElementById('proxySessionHistory');
    const invalidResourcesNode = document.getElementById('invalidResources');
    let autoRefreshHandle = null;
    let validatedLlmProgressHandle = null;
    const trendStorageKey = 'ashybulak_admin_trends_v1';
    const languageStorageKey = 'ashybulak_admin_lang_v1';
    let languageSelect = null;
    let lastDashboardData = null;
    let lastValidatedLlmPayload = null;
    let lastDispatcherStatusPayload = null;

    const I18N = {
      'ru': {
        pageTitle: 'AshybulakStroy AI HUB Admin',
        admin: 'Админка',
        lead: 'Одна таблица сверху вниз: каждая строка это модель, а лимиты подтягиваются из live-наблюдений провайдера и сохраненной оценки RPM/RPD.',
        refresh: 'Обновить',
        refreshLive: 'Обновить live-лимиты',
        proxyMode: 'Режим прокси',
        applyMode: 'Применить режим',
        language: 'Язык',
        autoRefresh: 'Автообновление',
        block1: 'Блок №1',
        block15: 'Блок №1.5',
        activeSessions: 'Активные прокси-сессии',
        block2: 'Блок №2',
        modelsAndLimits: 'Модели и лимиты',
        loadingData: 'Идет сбор данных и счетчиков. Подождите...',
        block3: 'Блок №3',
        recommendations: 'Рекомендации от ИИ',
        block4: 'Блок №4',
        validatedLlm: 'Проверенные модели LLM',
        validateRemaining: 'Проверить оставшиеся LLM',
        block5: 'Блок №5',
        proxyHistory: 'История прокси-сессий',
        block6: 'Блок №6',
        invalidResources: 'Invalid resources',
        invalidResourcesEmpty: 'Список invalid resources пока пуст',
        resource: 'Ресурс',
        reason: 'Причина',
        arrestedAt: 'Дата ареста',
        invalidUntil: 'Действует до',
        service: 'Сервис',
        providers: 'Провайдеры',
        models: 'Модели',
        afterFilter: 'после фильтра из',
        lastProbe: 'Последний probe',
        successful: 'успешно',
        provider: 'Провайдер',
        model: 'Модель',
        status: 'Статус',
        code: 'Код',
        startedAt: 'Начато',
        finishesAt: 'Завершится',
        finishedAt: 'Завершено',
        mode: 'Режим',
        noActiveSessions: 'Нет активных прокси-сессий',
        noCompletedSessions: 'Пока нет завершённых сессий',
        statusError: 'ошибка',
        statusFallback: 'fallback',
        statusMismatch: 'расхождение',
        statusOk: 'ok',
        statusSuccessSession: 'успешно',
        remainingRpm: 'Осталось RPM',
        remainingRpd: 'Осталось RPD',
        remainingTpm: 'Осталось токенов/мин',
        max: 'Макс',
        source: 'Источник',
        lastObserved: 'Последнее наблюдение',
        test: 'Проверка',
        testAction: 'Проверить',
        llmTitle: 'LLM модели',
        llmSub: 'Все языковые модели всех поставщиков.',
        audioTitle: 'Аудио распознавание',
        audioSub: 'Модели распознавания речи и транскрибации.',
        videoTitle: 'Видео модели',
        videoSub: 'Видео-модели и связанные генеративные видео сервисы.',
        otherTitle: 'Остальные модели',
        otherSub: 'Все остальные модели, которые не попали в первые три группы.',
        emptyGroup: 'В этой группе моделей нет',
        validatedSub: 'LLM-модели вне Блока №2, которые прошли отдельную текстовую проверку. Последняя проверка: {validatedAt}. Данные загружены из кэша. Кэш обновлён: {cacheAt}.',
        answerToTest: 'Ответ на тест',
        lastValidation: 'Последняя проверка',
        noValidated: 'Пока нет отдельно проверенных LLM-моделей',
        validatingRemaining: 'Идет проверка оставшихся LLM-моделей. Подождите...',
        requestsToTest: 'Запросы на тестирование',
        receivedResponses: 'Полученные ответы',
        didNotPass: 'Не прошло',
        liveRecsNoneTitle: 'Живых рекомендаций пока нет',
        liveRecsNoneText: 'Провайдеры ещё не отдали live-счётчики. Нажмите "Обновить live-лимиты" и подождите завершения сбора данных.',
        recBestNowTitle: 'Куда лучше отправлять запросы сейчас',
        recLowestNowTitle: 'Где ресурс заканчивается быстрее всего',
        recHeavyTitle: 'Кто лучше для тяжёлых запросов',
        recMostModelsTitle: 'Где сейчас больше всего пригодных моделей',
        recBestNowText: 'Сейчас самый свободный по остаткам RPM провайдер — {provider}. Осталось примерно {value} RPM.',
        recLowestNowText: 'Ближе всего к исчерпанию сейчас {provider}. Остаток RPM: {value}.',
        recHeavyText: 'Если запросы крупные по токенам, сейчас логичнее смотреть на {provider}. Осталось токенов в минуту: {value}.',
        recHeavyNoneText: 'Провайдеры не отдали счётчики токенов в минуту.',
        recMostModelsText: 'Больше всего моделей со статусом OK и live-лимитами сейчас у провайдера {provider}: {count}.',
        noModelData: 'Нет данных по моделям.',
        analyzing: 'Идет анализ',
        analyzingText: 'Собираем live-счетчики и готовим рекомендации...',
        failed: 'ошибка',
        checking: 'проверка...',
        na: 'n/a',
      },
      'kz': {
        pageTitle: 'AshybulakStroy AI HUB Admin',
        admin: 'УРєС–РјРґС–Рє РїР°РЅРµР»С–',
        lead: 'Бір кесте жоғарыдан төмен: әр жол бір модель, ал лимиттер провайдердің live-бақылауынан және сақталған RPM/RPD бағасынан алынады.',
        refresh: 'Жаңарту',
        refreshLive: 'Live-лимиттерді жаңарту',
        proxyMode: 'Прокси режимі',
        applyMode: 'Режимді қолдану',
        language: 'Тіл',
        autoRefresh: 'Автожаңарту',
        block1: 'Блок №1',
        block15: 'Блок №1.5',
        activeSessions: 'Белсенді прокси-сессиялар',
        block2: 'Блок №2',
        modelsAndLimits: 'Модельдер мен лимиттер',
        loadingData: 'Деректер мен есептегіштер жиналып жатыр. Күтіңіз...',
        block3: 'Блок №3',
        recommendations: 'AI ұсыныстары',
        block4: 'Блок №4',
        validatedLlm: 'Тексерілген LLM модельдері',
        validateRemaining: 'Қалған LLM-дерді тексеру',
        block5: 'Блок №5',
        proxyHistory: 'Прокси-сессия тарихы',
        service: 'Қызмет',
        providers: 'Провайдерлер',
        models: 'Модельдер',
        afterFilter: 'сүзгіден кейін',
        lastProbe: 'Соңғы probe',
        successful: 'сәтті',
        provider: 'Провайдер',
        model: 'Модель',
        status: 'Күй',
        code: 'Код',
        startedAt: 'Басталды',
        finishesAt: 'Аяқталады',
        finishedAt: 'Аяқталды',
        mode: 'Режим',
        noActiveSessions: 'Белсенді прокси-сессиялар жоқ',
        noCompletedSessions: 'Әзірге аяқталған сессиялар жоқ',
        statusError: 'қате',
        statusFallback: 'fallback',
        statusMismatch: 'айырмашылық',
        statusOk: 'ok',
        statusSuccessSession: 'сәтті',
        remainingRpm: 'Қалған RPM',
        remainingRpd: 'Қалған RPD',
        remainingTpm: 'Қалған токен/мин',
        max: 'Макс',
        source: 'Дереккөз',
        lastObserved: 'Соңғы бақылау',
        test: 'Тексеру',
        testAction: 'Тексеру',
        llmTitle: 'LLM модельдері',
        llmSub: 'Барлық жеткізушілердің тілдік модельдері.',
        audioTitle: 'Аудио тану',
        audioSub: 'Сөйлеуді тану және транскрипция модельдері.',
        videoTitle: 'Видео модельдер',
        videoSub: 'Видео модельдер және генеративті видео сервистері.',
        otherTitle: 'Басқа модельдер',
        otherSub: 'Алғашқы үш топқа кірмеген барлық модельдер.',
        emptyGroup: 'Бұл топта модель жоқ',
        validatedSub: '№2 блоктан тыс, бөлек мәтіндік тексеруден өткен LLM-модельдер. Соңғы тексеру: {validatedAt}. Деректер кэштен жүктелді. Кэш жаңартылды: {cacheAt}.',
        answerToTest: 'Тест жауабы',
        lastValidation: 'Соңғы тексеру',
        noValidated: 'УР·С–СЂРіРµ Р±У©Р»РµРє С‚РµРєСЃРµСЂС–Р»РіРµРЅ LLM-РјРѕРґРµР»СЊРґРµСЂ Р¶РѕТ›',
        validatingRemaining: 'Қалған LLM-модельдер тексеріліп жатыр. Күтіңіз...',
        requestsToTest: 'Тест сұраулары',
        receivedResponses: 'Алынған жауаптар',
        didNotPass: 'Өтпеді',
        liveRecsNoneTitle: 'Live ұсыныстар әзірге жоқ',
        liveRecsNoneText: 'Провайдерлер live-есептегіштерді әлі берген жоқ. "Live-лимиттерді жаңарту" түймесін басып, аяқталғанын күтіңіз.',
        recBestNowTitle: 'Қазір сұрауды қайда жіберген дұрыс',
        recLowestNowTitle: 'Қай жерде ресурс тезірек таусылады',
        recHeavyTitle: 'Ауыр сұрауларға кім ыңғайлы',
        recMostModelsTitle: 'Қазір жарамды модельдер қайда көп',
        recBestNowText: 'Қазір RPM қалдығы бойынша ең бос провайдер — {provider}. Шамамен {value} RPM қалды.',
        recLowestNowText: 'Қазір таусылуға ең жақыны {provider}. RPM қалдығы: {value}.',
        recHeavyText: 'Егер сұраулар токен бойынша үлкен болса, қазір {provider} қараған дұрыс. Минутына қалған токен: {value}.',
        recHeavyNoneText: 'Провайдерлер минуттық токен есептегішін берген жоқ.',
        recMostModelsText: 'OK статусы және live-лимиттері бар модельдер ең көп провайдер — {provider}: {count}.',
        noModelData: 'Модельдер бойынша дерек жоқ.',
        analyzing: 'Талдау жүріп жатыр',
        analyzingText: 'Live-есептегіштер жиналып, ұсыныстар дайындалып жатыр...',
        failed: 'қате',
        checking: 'тексерілуде...',
        na: 'n/a',
      },
      'ar': {
        pageTitle: 'AshybulakStroy AI HUB Admin',
        admin: 'لوحة الإدارة',
        lead: 'جدول واحد من الأعلى إلى الأسفل: كل صف هو نموذج، ويتم جلب الحدود من المراقبة الحية للمزوّد ومن تقدير RPM/RPD المحفوظ.',
        refresh: 'تحديث',
        refreshLive: 'تحديث الحدود الحية',
        proxyMode: 'وضع البروكسي',
        applyMode: 'تطبيق الوضع',
        language: 'اللغة',
        autoRefresh: 'تحديث تلقائي',
        block1: 'الكتلة رقم 1',
        block15: 'الكتلة رقم 1.5',
        activeSessions: 'جلسات البروكسي النشطة',
        block2: 'الكتلة رقم 2',
        modelsAndLimits: 'النماذج والحدود',
        loadingData: 'يتم جمع البيانات والعدادات. يرجى الانتظار...',
        block3: 'الكتلة رقم 3',
        recommendations: 'توصيات الذكاء الاصطناعي',
        block4: 'الكتلة رقم 4',
        validatedLlm: 'نماذج LLM الموثقة',
        validateRemaining: 'فحص نماذج LLM المتبقية',
        block5: 'الكتلة رقم 5',
        proxyHistory: 'سجل جلسات البروكسي',
        service: 'الخدمة',
        providers: 'المزوّدون',
        models: 'النماذج',
        afterFilter: 'بعد التصفية من',
        lastProbe: 'آخر probe',
        successful: 'ناجح',
        provider: 'المزوّد',
        model: 'النموذج',
        status: 'الحالة',
        code: 'الرمز',
        startedAt: 'بدأ',
        finishesAt: 'سينتهي',
        finishedAt: 'انتهى',
        mode: 'الوضع',
        noActiveSessions: 'لا توجد جلسات بروكسي نشطة',
        noCompletedSessions: 'لا توجد جلسات مكتملة حتى الآن',
        statusError: 'خطأ',
        statusFallback: 'احتياطي',
        statusMismatch: 'اختلاف',
        statusOk: 'ok',
        statusSuccessSession: 'ناجح',
        remainingRpm: 'المتبقي RPM',
        remainingRpd: 'المتبقي RPD',
        remainingTpm: 'المتبقي توكن/دقيقة',
        max: 'الحد الأقصى',
        source: 'المصدر',
        lastObserved: 'آخر ملاحظة',
        test: 'الاختبار',
        testAction: 'فحص',
        llmTitle: 'نماذج LLM',
        llmSub: 'كل النماذج اللغوية من جميع المزوّدين.',
        audioTitle: 'التعرف على الصوت',
        audioSub: 'نماذج التعرف على الكلام والتفريغ.',
        videoTitle: 'نماذج الفيديو',
        videoSub: 'نماذج الفيديو والخدمات التوليدية المرتبطة بها.',
        otherTitle: 'نماذج أخرى',
        otherSub: 'جميع النماذج الأخرى التي لم تدخل في المجموعات الثلاث الأولى.',
        emptyGroup: 'لا توجد نماذج في هذه المجموعة',
        validatedSub: 'نماذج LLM خارج الكتلة رقم 2 التي اجتازت فحصاً نصياً منفصلاً. آخر فحص: {validatedAt}. البيانات محمّلة من الذاكرة المؤقتة. آخر تحديث للذاكرة المؤقتة: {cacheAt}.',
        answerToTest: 'إجابة الاختبار',
        lastValidation: 'آخر فحص',
        noValidated: 'لا توجد نماذج LLM موثقة بشكل منفصل حتى الآن',
        validatingRemaining: 'يتم فحص نماذج LLM المتبقية. يرجى الانتظار...',
        requestsToTest: 'طلبات الفحص',
        receivedResponses: 'الردود المستلمة',
        didNotPass: 'لم يجتز',
        liveRecsNoneTitle: 'لا توجد توصيات حية بعد',
        liveRecsNoneText: 'لم يرسل المزوّدون العدادات الحية بعد. اضغط "تحديث الحدود الحية" وانتظر اكتمال الجمع.',
        recBestNowTitle: 'إلى أين من الأفضل إرسال الطلبات الآن',
        recLowestNowTitle: 'أين يوشك المورد على النفاد',
        recHeavyTitle: 'من الأفضل للطلبات الثقيلة',
        recMostModelsTitle: 'أين يوجد أكبر عدد من النماذج المناسبة الآن',
        recBestNowText: 'المزوّد الأكثر حرية الآن حسب RPM المتبقي هو {provider}. المتبقي تقريباً {value} RPM.',
        recLowestNowText: 'الأقرب إلى النفاد الآن هو {provider}. المتبقي من RPM: {value}.',
        recHeavyText: 'إذا كانت الطلبات كبيرة من حيث التوكنات، فالأفضل الآن النظر إلى {provider}. التوكنات المتبقية في الدقيقة: {value}.',
        recHeavyNoneText: 'لم يرسل المزوّدون عدادات التوكنات في الدقيقة.',
        recMostModelsText: 'أكبر عدد من النماذج ذات الحالة OK والحدود الحية الآن لدى المزوّد {provider}: {count}.',
        noModelData: 'لا توجد بيانات عن النماذج.',
        analyzing: 'جارٍ التحليل',
        analyzingText: 'نجمع العدادات الحية ونجهز التوصيات...',
        failed: 'خطأ',
        checking: 'جارٍ الفحص...',
        na: 'n/a',
      },
      'en-gb': {
        pageTitle: 'AshybulakStroy AI HUB Admin',
        admin: 'Admin Panel',
        lead: 'One table from top to bottom: each row is a model, and limits are pulled from live provider observations and the saved RPM/RPD estimate.',
        refresh: 'Refresh',
        refreshLive: 'Refresh live limits',
        proxyMode: 'Proxy mode',
        applyMode: 'Apply mode',
        language: 'Language',
        autoRefresh: 'Auto refresh',
        block1: 'Block #1',
        block15: 'Block #1.5',
        activeSessions: 'Active proxy sessions',
        block2: 'Block #2',
        modelsAndLimits: 'Models and limits',
        loadingData: 'Collecting data and counters. Please wait...',
        block3: 'Block #3',
        recommendations: 'AI recommendations',
        block4: 'Block #4',
        validatedLlm: 'Validated LLM models',
        validateRemaining: 'Validate remaining LLMs',
        block5: 'Block #5',
        proxyHistory: 'Proxy session history',
        block6: 'Block #6',
        invalidResources: 'Invalid resources',
        invalidResourcesEmpty: 'No invalid resources yet',
        resource: 'Resource',
        reason: 'Reason',
        arrestedAt: 'Arrested at',
        invalidUntil: 'Invalid until',
        service: 'Service',
        providers: 'Providers',
        models: 'Models',
        afterFilter: 'after filtering from',
        lastProbe: 'Last probe',
        successful: 'successful',
        provider: 'Provider',
        model: 'Model',
        status: 'Status',
        code: 'Code',
        startedAt: 'Started',
        finishesAt: 'Finishes',
        finishedAt: 'Finished',
        mode: 'Mode',
        noActiveSessions: 'No active proxy sessions',
        noCompletedSessions: 'No completed sessions yet',
        statusError: 'error',
        statusFallback: 'fallback',
        statusMismatch: 'mismatch',
        statusOk: 'ok',
        statusSuccessSession: 'successful',
        remainingRpm: 'Remaining RPM',
        remainingRpd: 'Remaining RPD',
        remainingTpm: 'Remaining tokens/min',
        max: 'Max',
        source: 'Source',
        lastObserved: 'Last observed',
        test: 'Test',
        testAction: 'Test',
        llmTitle: 'LLM models',
        llmSub: 'All language models from all providers.',
        audioTitle: 'Audio recognition',
        audioSub: 'Speech recognition and transcription models.',
        videoTitle: 'Video models',
        videoSub: 'Video models and related generative video services.',
        otherTitle: 'Other models',
        otherSub: 'All remaining models that do not fit the first three groups.',
        emptyGroup: 'There are no models in this group',
        validatedSub: 'LLM models outside Block #2 that passed a separate text validation. Last validation: {validatedAt}. Data loaded from cache. Cache updated: {cacheAt}.',
        answerToTest: 'Test reply',
        lastValidation: 'Last validation',
        noValidated: 'No separately validated LLM models yet',
        validatingRemaining: 'Validating remaining LLM models. Please wait...',
        requestsToTest: 'Validation requests',
        receivedResponses: 'Received responses',
        didNotPass: 'Did not pass',
        liveRecsNoneTitle: 'No live recommendations yet',
        liveRecsNoneText: 'Providers have not returned live counters yet. Press "Refresh live limits" and wait for collection to finish.',
        recBestNowTitle: 'Where to send requests right now',
        recLowestNowTitle: 'Where the resource is running out fastest',
        recHeavyTitle: 'Best option for heavy requests',
        recMostModelsTitle: 'Where the most usable models are right now',
        recBestNowText: 'The freest provider by remaining RPM right now is {provider}. Roughly {value} RPM remain.',
        recLowestNowText: 'The provider closest to exhaustion right now is {provider}. Remaining RPM: {value}.',
        recHeavyText: 'If requests are token-heavy, it makes most sense to look at {provider} right now. Remaining tokens per minute: {value}.',
        recHeavyNoneText: 'Providers did not return tokens-per-minute counters.',
        recMostModelsText: 'The provider with the most models in OK status and with live limits right now is {provider}: {count}.',
        noModelData: 'No model data.',
        analyzing: 'Analysing',
        analyzingText: 'Collecting live counters and preparing recommendations...',
        failed: 'failed',
        checking: 'checking...',
        na: 'n/a',
      },
      'en-us': {
        pageTitle: 'AshybulakStroy AI HUB Admin',
        admin: 'Admin Panel',
        lead: 'One table from top to bottom: each row is a model, and limits are pulled from live provider observations and the saved RPM/RPD estimate.',
        refresh: 'Refresh',
        refreshLive: 'Refresh live limits',
        proxyMode: 'Proxy mode',
        applyMode: 'Apply mode',
        language: 'Language',
        autoRefresh: 'Auto refresh',
        block1: 'Block #1',
        block15: 'Block #1.5',
        activeSessions: 'Active proxy sessions',
        block2: 'Block #2',
        modelsAndLimits: 'Models and limits',
        loadingData: 'Collecting data and counters. Please wait...',
        block3: 'Block #3',
        recommendations: 'AI recommendations',
        block4: 'Block #4',
        validatedLlm: 'Validated LLM models',
        validateRemaining: 'Validate remaining LLMs',
        block5: 'Block #5',
        proxyHistory: 'Proxy session history',
        block6: 'Block #6',
        invalidResources: 'Invalid resources',
        invalidResourcesEmpty: 'No invalid resources yet',
        resource: 'Resource',
        reason: 'Reason',
        arrestedAt: 'Arrested at',
        invalidUntil: 'Invalid until',
        service: 'Service',
        providers: 'Providers',
        models: 'Models',
        afterFilter: 'after filtering from',
        lastProbe: 'Last probe',
        successful: 'successful',
        provider: 'Provider',
        model: 'Model',
        status: 'Status',
        code: 'Code',
        startedAt: 'Started',
        finishesAt: 'Finishes',
        finishedAt: 'Finished',
        mode: 'Mode',
        noActiveSessions: 'No active proxy sessions',
        noCompletedSessions: 'No completed sessions yet',
        statusError: 'error',
        statusFallback: 'fallback',
        statusMismatch: 'mismatch',
        statusOk: 'ok',
        statusSuccessSession: 'successful',
        remainingRpm: 'Remaining RPM',
        remainingRpd: 'Remaining RPD',
        remainingTpm: 'Remaining tokens/min',
        max: 'Max',
        source: 'Source',
        lastObserved: 'Last observed',
        test: 'Test',
        testAction: 'Test',
        llmTitle: 'LLM models',
        llmSub: 'All language models from all providers.',
        audioTitle: 'Audio recognition',
        audioSub: 'Speech recognition and transcription models.',
        videoTitle: 'Video models',
        videoSub: 'Video models and related generative video services.',
        otherTitle: 'Other models',
        otherSub: 'All remaining models that do not fit the first three groups.',
        emptyGroup: 'There are no models in this group',
        validatedSub: 'LLM models outside Block #2 that passed a separate text validation. Last validation: {validatedAt}. Data loaded from cache. Cache updated: {cacheAt}.',
        answerToTest: 'Test reply',
        lastValidation: 'Last validation',
        noValidated: 'No separately validated LLM models yet',
        validatingRemaining: 'Validating remaining LLM models. Please wait...',
        requestsToTest: 'Validation requests',
        receivedResponses: 'Received responses',
        didNotPass: 'Did not pass',
        liveRecsNoneTitle: 'No live recommendations yet',
        liveRecsNoneText: 'Providers have not returned live counters yet. Press "Refresh live limits" and wait for collection to finish.',
        recBestNowTitle: 'Where to send requests right now',
        recLowestNowTitle: 'Where the resource is running out fastest',
        recHeavyTitle: 'Best option for heavy requests',
        recMostModelsTitle: 'Where the most usable models are right now',
        recBestNowText: 'The freest provider by remaining RPM right now is {provider}. Roughly {value} RPM remain.',
        recLowestNowText: 'The provider closest to exhaustion right now is {provider}. Remaining RPM: {value}.',
        recHeavyText: 'If requests are token-heavy, it makes most sense to look at {provider} right now. Remaining tokens per minute: {value}.',
        recHeavyNoneText: 'Providers did not return tokens-per-minute counters.',
        recMostModelsText: 'The provider with the most models in OK status and with live limits right now is {provider}: {count}.',
        noModelData: 'No model data.',
        analyzing: 'Analyzing',
        analyzingText: 'Collecting live counters and preparing recommendations...',
        failed: 'failed',
        checking: 'checking...',
        na: 'n/a',
      },
      'zh-cn': {
        pageTitle: 'AshybulakStroy AI HUB 管理面板',
        admin: '管理面板',
        lead: 'дёЂдёЄи‡ЄдёЉиЂЊдё‹зљ„иЎЁж јпјљжЇЏдёЂиЎЊйѓЅжЇдёЂдёЄжЁЎећ‹пјЊй™ђе€¶жќҐи‡ЄжЏђдѕ›ж–№зљ„е®ћж—¶и§‚жµ‹е’Ње·Ідїќе­зљ„ RPM/RPD дј°и®ЎгЂ‚',
        refresh: '刷新',
        refreshLive: '刷新实时限额',
        proxyMode: '代理模式',
        applyMode: '应用模式',
        language: '语言',
        autoRefresh: '自动刷新',
        block1: '模块 #1',
        block15: '模块 #1.5',
        activeSessions: '活跃代理会话',
        block2: '模块 #2',
        modelsAndLimits: '模型与限额',
        loadingData: '正在收集数据和计数器，请稍候...',
        block3: '模块 #3',
        recommendations: 'AI 建议',
        block4: '模块 #4',
        validatedLlm: '已验证的 LLM 模型',
        validateRemaining: '验证剩余 LLM',
        block5: '模块 #5',
        proxyHistory: '代理会话历史',
        service: '服务',
        providers: '提供方',
        models: '模型',
        afterFilter: '筛选后，原始数量',
        lastProbe: '最近 probe',
        successful: '成功',
        provider: '提供方',
        model: '模型',
        status: '状态',
        code: '代码',
        startedAt: '开始时间',
        finishesAt: '结束中',
        finishedAt: '完成时间',
        mode: '模式',
        noActiveSessions: '没有活跃代理会话',
        noCompletedSessions: 'иїжІЎжњ‰е·Іе®Њж€ђдјљиЇќ',
        statusError: '错误',
        statusFallback: '回退',
        statusMismatch: '不一致',
        statusOk: 'ok',
        statusSuccessSession: '成功',
        remainingRpm: '剩余 RPM',
        remainingRpd: '剩余 RPD',
        remainingTpm: '剩余 token/分钟',
        max: '最大值',
        source: '来源',
        lastObserved: '最后观测',
        test: '测试',
        testAction: '测试',
        llmTitle: 'LLM 模型',
        llmSub: '所有提供方的语言模型。',
        audioTitle: '音频识别',
        audioSub: '语音识别和转录模型。',
        videoTitle: '视频模型',
        videoSub: '视频模型和相关生成式视频服务。',
        otherTitle: '其他模型',
        otherSub: '未进入前三组的所有其他模型。',
        emptyGroup: '此分组中没有模型',
        validatedSub: 'дЅЌдєЋжЁЎеќ— #2 д№‹е¤–е№¶йЂљиї‡еЌ•з‹¬ж–‡жњ¬йЄЊиЇЃзљ„ LLM жЁЎећ‹гЂ‚жњЂиї‘йЄЊиЇЃпјљ{validatedAt}гЂ‚ж•°жЌ®жќҐи‡Єзј“е­гЂ‚зј“е­ж›ґж–°ж—¶й—ґпјљ{cacheAt}гЂ‚',
        answerToTest: '测试回复',
        lastValidation: '最近验证',
        noValidated: '暂无单独验证的 LLM 模型',
        validatingRemaining: '正在验证剩余 LLM 模型，请稍候...',
        requestsToTest: '测试请求',
        receivedResponses: '收到的响应',
        didNotPass: '未通过',
        liveRecsNoneTitle: '暂无实时建议',
        liveRecsNoneText: '提供方尚未返回实时计数器。请点击“刷新实时限额”并等待收集完成。',
        recBestNowTitle: '当前最适合发送请求的位置',
        recLowestNowTitle: '资源消耗最快的位置',
        recHeavyTitle: '重请求的最佳选项',
        recMostModelsTitle: '当前可用模型最多的位置',
        recBestNowText: 'еЅ“е‰ЌжЊ‰е‰©дЅ™ RPM зњ‹жњЂз©єй—Ізљ„жЏђдѕ›ж–№жЇ {provider}гЂ‚е¤§зє¦е‰©дЅ™ {value} RPMгЂ‚',
        recLowestNowText: 'еЅ“е‰ЌжњЂжЋҐиї‘иЂ—е°Ѕзљ„жЏђдѕ›ж–№жЇ {provider}гЂ‚е‰©дЅ™ RPMпјљ{value}гЂ‚',
        recHeavyText: '如果请求很重、token 很多，当前更适合看 {provider}。每分钟剩余 token：{value}。',
        recHeavyNoneText: '提供方没有返回每分钟 token 计数器。',
        recMostModelsText: 'еЅ“е‰Ќж‹Ґжњ‰жњЂе¤љ OK зЉ¶жЂЃдё”её¦ live й™ђйўќжЁЎећ‹зљ„жЏђдѕ›ж–№жЇ {provider}пјљ{count}гЂ‚',
        noModelData: '没有模型数据。',
        analyzing: '分析中',
        analyzingText: '正在收集实时计数器并准备建议...',
        failed: '失败',
        checking: '测试中...',
        na: 'n/a',
      },
    };

    function repairMojibake(value) {
      if (typeof value !== 'string') return value;
      if (!/[À-ÿ]/.test(value)) return value;
      try {
        const bytes = Uint8Array.from(value, (char) => char.charCodeAt(0) & 0xff);
        const decoded = new TextDecoder('utf-8', { fatal: false }).decode(bytes);
        const sourceNoise = (value.match(/[À-ÿ]/g) || []).length;
        const decodedNoise = (decoded.match(/[À-ÿ]/g) || []).length;
        return decodedNoise < sourceNoise ? decoded : value;
      } catch {
        return value;
      }
    }

    Object.values(I18N).forEach((dict) => {
      Object.keys(dict).forEach((key) => {
        dict[key] = repairMojibake(dict[key]);
      });
    });

    function currentLang() {
      const saved = localStorage.getItem(languageStorageKey) || 'ru';
      return I18N[saved] ? saved : 'ru';
    }

    function t(key, vars = {}) {
      const lang = currentLang();
      const dict = I18N[lang] || I18N['ru'];
      const fallback = I18N['ru'][key] ?? key;
      let text = dict[key] ?? fallback;
      Object.entries(vars).forEach(([name, value]) => {
        text = text.replaceAll(`{${name}}`, String(value ?? ''));
      });
      return text;
    }

    function ensureLanguageControl() {
      if (document.getElementById('languageSelect')) {
        languageSelect = document.getElementById('languageSelect');
        return;
      }
      const actions = document.querySelector('.actions');
      if (!actions) return;
      const label = document.createElement('label');
      label.className = 'refresh-control';
      label.innerHTML = `
        <span id="languageLabel">${t('language')}</span>
        <select id="languageSelect">
          <option value="ru">СНГ / Русский</option>
          <option value="kz">Азия / Қазақша</option>
          <option value="ar">العربية</option>
          <option value="en-gb">Europe / English</option>
          <option value="en-us">America / English</option>
          <option value="zh-cn">China / 中文</option>
        </select>
      `;
      const autoRefreshControl = Array.from(actions.querySelectorAll('.refresh-control')).at(-1);
      if (autoRefreshControl) {
        actions.insertBefore(label, autoRefreshControl);
      } else {
        actions.appendChild(label);
      }
      languageSelect = document.getElementById('languageSelect');
    }

    function applyLanguage() {
      const lang = currentLang();
      document.documentElement.lang = lang;
      document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
      document.title = t('pageTitle');
      const eyebrow = document.querySelector('.eyebrow');
      const lead = document.querySelector('.lead');
      const panelLabels = document.querySelectorAll('.panel > .label');
      const actionControls = document.querySelectorAll('.actions .refresh-control span');
      if (eyebrow) eyebrow.textContent = t('admin');
      if (lead) lead.textContent = t('lead');
      if (document.getElementById('refreshAll')) document.getElementById('refreshAll').textContent = t('refresh');
      if (document.getElementById('refreshLive')) document.getElementById('refreshLive').textContent = t('refreshLive');
      if (document.getElementById('applyProxyMode')) document.getElementById('applyProxyMode').textContent = t('applyMode');
      if (document.getElementById('refreshValidatedLlm')) document.getElementById('refreshValidatedLlm').textContent = t('validateRemaining');
      if (actionControls[0]) actionControls[0].textContent = t('proxyMode');
      if (actionControls[1]) actionControls[1].textContent = t('language');
      if (actionControls[2]) actionControls[2].textContent = t('autoRefresh');
      if (panelLabels[0]) panelLabels[0].textContent = t('block1');
      if (panelLabels[1]) panelLabels[1].textContent = t('block15');
      if (panelLabels[2]) panelLabels[2].textContent = t('activeSessions');
      if (panelLabels[3]) panelLabels[3].textContent = t('block2');
      if (panelLabels[4]) panelLabels[4].textContent = t('modelsAndLimits');
      if (panelLabels[5]) panelLabels[5].textContent = t('block3');
      if (panelLabels[6]) panelLabels[6].textContent = t('recommendations');
      if (panelLabels[7]) panelLabels[7].textContent = t('block4');
      if (panelLabels[8]) panelLabels[8].textContent = t('validatedLlm');
      if (panelLabels[9]) panelLabels[9].textContent = t('block5');
      if (panelLabels[10]) panelLabels[10].textContent = t('proxyHistory');
      if (panelLabels[11]) panelLabels[11].textContent = t('block6');
      if (panelLabels[12]) panelLabels[12].textContent = t('invalidResources');
      loadingState.textContent = t('loadingData');
      if (languageSelect) {
        languageSelect.value = lang;
      }
    }

    function localiseRenderedContent() {
      const statNodes = overviewStats.querySelectorAll('.stat');
      if (statNodes[0]) {
        const label = statNodes[0].querySelector('.label');
        if (label) label.textContent = t('service');
      }
      if (statNodes[1]) {
        const label = statNodes[1].querySelector('.label');
        if (label) label.textContent = t('providers');
      }
      if (statNodes[2]) {
        const label = statNodes[2].querySelector('.label');
        const sub = statNodes[2].querySelector('.sub');
        if (label) label.textContent = t('models');
        if (sub) {
          const match = sub.textContent.match(/(\d+)/);
          sub.textContent = `${t('afterFilter')}: ${match ? match[1] : t('na')}`;
        }
      }
      if (statNodes[3]) {
        const label = statNodes[3].querySelector('.label');
        const sub = statNodes[3].querySelector('.sub');
        if (label) label.textContent = t('lastProbe');
        if (sub) {
          const match = sub.textContent.match(/(\d+)/);
          sub.textContent = `${t('successful')}: ${match ? match[1] : 0}`;
        }
      }

      const groupedSections = groupedTables.querySelectorAll('section');
      if (groupedSections[0]) {
        groupedSections[0].querySelector('.group-title').textContent = t('llmTitle');
        groupedSections[0].querySelector('.group-sub').textContent = t('llmSub');
      }
      if (groupedSections[1]) {
        groupedSections[1].querySelector('.group-title').textContent = t('audioTitle');
        groupedSections[1].querySelector('.group-sub').textContent = t('audioSub');
      }
      if (groupedSections[2]) {
        groupedSections[2].querySelector('.group-title').textContent = t('videoTitle');
        groupedSections[2].querySelector('.group-sub').textContent = t('videoSub');
      }
      if (groupedSections[3]) {
        groupedSections[3].querySelector('.group-title').textContent = t('otherTitle');
        groupedSections[3].querySelector('.group-sub').textContent = t('otherSub');
      }

      groupedTables.querySelectorAll('thead tr').forEach((row) => {
        const headers = row.querySelectorAll('th');
        if (headers.length === 10) {
          headers[0].textContent = t('provider');
          headers[1].textContent = t('model');
          headers[2].textContent = t('remainingRpm');
          headers[3].textContent = t('remainingRpd');
          headers[4].textContent = t('remainingTpm');
          headers[5].textContent = t('max');
          headers[6].textContent = t('source');
          headers[7].textContent = t('status');
          headers[8].textContent = t('lastObserved');
          headers[9].textContent = t('test');
        }
      });

      groupedTables.querySelectorAll('.empty').forEach((node) => {
        if (node.textContent.includes('РјРѕРґРµР»') || node.textContent.includes('Р СР С•Р Т‘Р ВµР В»')) {
          node.textContent = t('emptyGroup');
        }
      });

      validatedLlmNode.querySelectorAll('.group-title').forEach((node) => {
        node.textContent = t('validatedLlm');
      });
      const validatedSub = validatedLlmNode.querySelector('.group-sub');
      if (validatedSub) {
        const metaText = validatedSub.textContent;
        const dates = metaText.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|n\/a)/g) || [];
        validatedSub.textContent = t('validatedSub', {
          validatedAt: dates[0] || t('na'),
          cacheAt: dates[1] || t('na'),
        });
      }
      validatedLlmNode.querySelectorAll('thead tr').forEach((row) => {
        const headers = row.querySelectorAll('th');
        if (headers.length === 5) {
          headers[0].textContent = t('provider');
          headers[1].textContent = t('model');
          headers[2].textContent = t('answerToTest');
          headers[3].textContent = t('lastValidation');
          headers[4].textContent = t('test');
        }
      });
      validatedLlmNode.querySelectorAll('.empty').forEach((node) => {
        node.textContent = t('noValidated');
      });

      invalidResourcesNode.querySelectorAll('thead tr').forEach((row) => {
        const headers = row.querySelectorAll('th');
        if (headers.length === 6) {
          headers[0].textContent = t('resource');
          headers[1].textContent = t('code');
          headers[2].textContent = t('reason');
          headers[3].textContent = t('source');
          headers[4].textContent = t('arrestedAt');
          headers[5].textContent = t('invalidUntil');
        }
      });
      invalidResourcesNode.querySelectorAll('.empty').forEach((node) => {
        node.textContent = t('invalidResourcesEmpty');
      });

      document.querySelectorAll('[data-provider]').forEach((button) => {
        button.textContent = t('testAction');
      });

      document.querySelectorAll('td.status-ok, td.status-error, td.status-warn').forEach((cell) => {
        const value = cell.textContent.trim().toLowerCase();
        if (value === 'ok') cell.textContent = t('statusOk');
        if (value === 'успешно' || value === 'successful' || value === 'success') cell.textContent = t('statusSuccessSession');
        if (value === 'ошибка' || value === 'error') cell.textContent = t('statusError');
        if (value === 'fallback') cell.textContent = t('statusFallback');
        if (value === 'расхождение' || value === 'mismatch') cell.textContent = t('statusMismatch');
      });
    }

    function fmt(value) {
      return value === null || value === undefined || value === '' ? t('na') : String(value);
    }

    function fmtGmtPlus5(value) {
      if (!value) return t('na');
      const parsed = Date.parse(value);
      if (Number.isNaN(parsed)) return fmt(value);
      const shifted = new Date(parsed + (5 * 60 * 60 * 1000));
      const yy = String(shifted.getUTCFullYear()).slice(-2);
      const mm = String(shifted.getUTCMonth() + 1).padStart(2, '0');
      const dd = String(shifted.getUTCDate()).padStart(2, '0');
      const hh = String(shifted.getUTCHours()).padStart(2, '0');
      const mi = String(shifted.getUTCMinutes()).padStart(2, '0');
      const ss = String(shifted.getUTCSeconds()).padStart(2, '0');
      return `${hh}:${mi}:${ss} ${dd}-${mm}-${yy}`;
    }

    function fmtDurationSeconds(startedAt, finishedAt) {
      const started = Date.parse(startedAt);
      const finished = Date.parse(finishedAt);
      if (Number.isNaN(started) || Number.isNaN(finished)) return t('na');
      const seconds = Math.max(0, (finished - started) / 1000);
      return `${seconds.toFixed(2)} sec`;
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

    function modelsStatExtra(totalBeforeFilter, invalidCount) {
      const invalidTotal = Number(invalidCount || 0);
      if (invalidTotal > 0) {
        return `${t('afterFilter')}: ${fmt(totalBeforeFilter)}<br><span class="danger-text">В карантине: ${fmt(invalidTotal)}</span>`;
      }
      return `${t('afterFilter')}: ${fmt(totalBeforeFilter)}`;
    }

    function modelsStatCard(value, totalBeforeFilter, invalidCount) {
      const invalidTotal = Number(invalidCount || 0);
      return `
        <div class="stat">
          <div class="label">${t('models')}</div>
          <div class="value">${fmt(value)}</div>
          <div class="sub">${t('afterFilter')}: ${fmt(totalBeforeFilter)}</div>
          ${invalidTotal > 0 ? `<div class="danger-text">В карантине: ${fmt(invalidTotal)}</div>` : ''}
        </div>
      `;
    }

    function escapeAttr(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function errorCodeLabel(code) {
      const normalized = String(code ?? '').trim();
      const map = {
        '400': 'Bad Request',
        '401': 'Unauthorized',
        '402': 'Payment Required',
        '403': 'Forbidden',
        '404': 'Not Found',
        '408': 'Request Timeout',
        '409': 'Conflict',
        '410': 'Gone',
        '413': 'Payload Too Large',
        '422': 'Unprocessable Entity',
        '425': 'Too Early',
        '429': 'Too Many Requests',
        '500': 'Internal Server Error',
        '502': 'Bad Gateway',
        '503': 'Service Unavailable',
        '504': 'Gateway Timeout',
      };
      return map[normalized] || 'HTTP Error';
    }

    function errorCodeTooltip(session, statusCode) {
      if (!statusCode) return '';
      const detail = String(session?.detail || '').trim();
      const base = `${statusCode} ${errorCodeLabel(statusCode)}`;
      return detail ? `${base}. ${detail}` : base;
    }

    function sessionRowHtml(session) {
      const statusCode = session.status_code === null || session.status_code === undefined || session.status_code === '' ? '' : String(session.status_code);
      const rowClass = session.status === 'error' ? ' class="error"' : '';
      return `
        <tr${rowClass}>
          <td><span class="pill">${fmt(session.provider)}</span></td>
          <td class="mono">${fmt(session.model)}</td>
          <td>${session.status === 'success' ? t('statusSuccessSession') : session.status === 'error' ? t('statusError') : fmt(session.status)}</td>
          <td>${statusCode}</td>
          <td class="mono">${fmt(session.started_at)}</td>
          <td class="mono">${fmt(session.finished_at)}</td>
          <td>${fmt(session.mode)}</td>
        </tr>
      `;
    }

    function historySessionRowHtml(session) {
      const statusCode = session.status_code === null || session.status_code === undefined || session.status_code === '' ? '' : String(session.status_code);
      const rowClass = statusCode ? ' class="error"' : session.status === 'error' ? ' class="error"' : '';
      const codeTitle = statusCode ? ` title="${escapeAttr(errorCodeTooltip(session, statusCode))}"` : '';
      return `
        <tr${rowClass}>
          <td><span class="pill">${fmt(session.provider)}</span></td>
          <td class="mono">${fmt(session.model)}</td>
          <td>${session.status === 'success' ? t('statusSuccessSession') : session.status === 'error' ? t('statusError') : fmt(session.status)}</td>
          <td${codeTitle}>${statusCode}</td>
          <td class="mono">${fmtGmtPlus5(session.started_at)}</td>
          <td class="mono">${fmtDurationSeconds(session.started_at, session.finished_at)}</td>
          <td>${fmt(session.mode)}</td>
        </tr>
      `;
    }

    function proxyHistorySummary(sessions) {
      const grouped = new Map();
      (sessions || []).forEach((session) => {
        const provider = fmt(session.provider);
        grouped.set(provider, (grouped.get(provider) || 0) + 1);
      });
      const parts = Array.from(grouped.entries())
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .map(([provider, count]) => `${provider}: ${count}`);
      const total = (sessions || []).length;
      return `<div class="group-sub">Провайдеры в последних ${total} сессиях: ${parts.join(' | ')}</div>`;
    }

    function activeSessionsSection(rowsHtml) {
      return `
        <section>
          <h2 class="group-title">${t('activeSessions')}</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>${t('provider')}</th>
                  <th>${t('model')}</th>
                  <th>${t('status')}</th>
                  <th>${t('code')}</th>
                  <th>${t('startedAt')}</th>
                  <th>${t('finishesAt')}</th>
                  <th>${t('mode')}</th>
                </tr>
              </thead>
              <tbody>${rowsHtml || `<tr><td colspan="7" class="empty">${t('noActiveSessions')}</td></tr>`}</tbody>
            </table>
          </div>
        </section>
      `;
    }

    function proxyHistorySection(rowsHtml) {
      return `
        <section>
          <h2 class="group-title">${t('proxyHistory')}</h2>
          ${proxyHistorySummary(lastDispatcherStatusPayload?.completed_sessions || [])}
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>${t('provider')}</th>
                  <th>${t('model')}</th>
                  <th>${t('status')}</th>
                  <th>${t('code')}</th>
                  <th>${t('startedAt')} GMT+5</th>
                  <th>sec</th>
                  <th>${t('mode')}</th>
                </tr>
              </thead>
              <tbody>${rowsHtml || `<tr><td colspan="7" class="empty">${t('noCompletedSessions')}</td></tr>`}</tbody>
            </table>
          </div>
        </section>
      `;
    }

    function invalidResourceRowHtml(item) {
      const sourceLabel = item.blocking === false ? `${fmt(item.source)} / observe` : `${fmt(item.source)} / blocking`;
      return `
        <tr class="invalid-resource-row">
          <td class="mono status-error">${fmt(item.resource_id)}</td>
          <td>${fmt(item.status_code)}</td>
          <td>${fmt(item.reason)}</td>
          <td>${sourceLabel}</td>
          <td class="mono">${formatGmtPlus5(item.arrested_at)}</td>
          <td class="mono">${formatGmtPlus5(item.invalid_until)}</td>
        </tr>
      `;
    }

    function invalidResourcesSection(items) {
      const rowsHtml = (items || []).map((item) => invalidResourceRowHtml(item)).join('');
      return `
        <section>
          <h2 class="group-title">${t('invalidResources')}</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>${t('resource')}</th>
                  <th>${t('code')}</th>
                  <th>${t('reason')}</th>
                  <th>${t('source')}</th>
                  <th>${t('arrestedAt')}</th>
                  <th>${t('invalidUntil')}</th>
                </tr>
              </thead>
              <tbody>${rowsHtml || `<tr><td colspan="6" class="empty">${t('invalidResourcesEmpty')}</td></tr>`}</tbody>
            </table>
          </div>
        </section>
      `;
    }

    function renderDispatcherStatus(payload) {
      lastDispatcherStatusPayload = payload;
      if (proxyModeSelect) {
        proxyModeSelect.value = payload.proxy_mode || 'FAST';
      }
      activeProxySessionsNode.innerHTML = payload.active_sessions?.length
        ? activeSessionsSection(payload.active_sessions.map(sessionRowHtml).join(''))
        : `<div class="empty">${t('noActiveSessions')}</div>`;
      proxySessionHistoryNode.innerHTML = payload.completed_sessions?.length
        ? proxyHistorySection(payload.completed_sessions.map(historySessionRowHtml).join(''))
        : `<div class="empty">${t('noCompletedSessions')}</div>`;
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
      const yy = String(shifted.getUTCFullYear()).slice(-2);
      return `${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}:${pad(shifted.getUTCSeconds())} ` +
        `${pad(shifted.getUTCDate())}-${pad(shifted.getUTCMonth() + 1)}-${yy}`;
    }

    function eligibilityStatus(liveItem, estimate) {
      if (liveItem?.last_error) {
        return { text: t('statusError'), cls: 'status-error', row: 'error' };
      }
      if (liveItem?.limits?.source === 'fallback_default') {
        return { text: t('statusFallback'), cls: 'status-warn', row: 'warn' };
      }
      const liveRpm = observedRpm(liveItem);
      if (estimate?.estimated_rpm && liveRpm && String(estimate.estimated_rpm) !== String(liveRpm)) {
        return { text: t('statusMismatch'), cls: 'status-warn', row: 'warn' };
      }
      return { text: t('statusOk'), cls: 'status-ok', row: '' };
    }

    function maxBundle(liveItem, estimate) {
      return {
        maxRpm: observedRpm(liveItem) ?? estimate?.estimated_rpm ?? null,
        maxRpd: observedRpd(liveItem) ?? estimate?.estimated_rpd ?? null,
        maxTpm: liveItem?.limits?.tokens?.minute?.limit ?? null,
      };
    }

    function rowStatus(routeItem, liveItem, estimate) {
      if (routeItem?.last_session_status === 'success') {
        return { text: t('statusSuccessSession'), cls: 'status-ok', row: '' };
      }
      if (routeItem?.last_session_status === 'error') {
        return { text: t('statusError'), cls: 'status-error', row: 'error' };
      }
      return eligibilityStatus(liveItem, estimate);
    }

    function rowHtml(model, liveItem, estimate, trendInfo, routeItem) {
      const provider = model.provider || 'unknown';
      const status = rowStatus(routeItem, liveItem, estimate);
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
            <button data-provider="${provider}" data-model="${fmt(model.id)}">${t('testAction')}</button>
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
            <button data-provider="${provider}" data-model="${fmt(model.id)}">${t('testAction')}</button>
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
        hay.includes('gemma') ||
        hay.includes('glm') ||
        hay.includes('qwen') ||
        hay.includes('deepseek') ||
        hay.includes('claude') ||
        hay.includes('mistral') ||
        hay.includes('allam') ||
        hay.includes('minimax') ||
        hay.includes('compound') ||
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
      return eligibilityStatus(liveItem, estimate).text === 'ok';
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
          recommendationCard(t('liveRecsNoneTitle'), t('liveRecsNoneText'))
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
          t('recBestNowTitle'),
          bestByRpm ? t('recBestNowText', { provider: bestByRpm.provider, value: fmt(bestByRpm.rpmRemaining) }) : t('noModelData')
        ),
        recommendationCard(
          t('recLowestNowTitle'),
          lowestByRpm ? t('recLowestNowText', { provider: lowestByRpm.provider, value: fmt(lowestByRpm.rpmRemaining) }) : t('noModelData')
        ),
        recommendationCard(
          t('recHeavyTitle'),
          bestByTokens ? t('recHeavyText', { provider: bestByTokens.provider, value: fmt(bestByTokens.tpmRemaining) }) : t('recHeavyNoneText')
        ),
        recommendationCard(
          t('recMostModelsTitle'),
          modelCounts[0] ? t('recMostModelsText', { provider: modelCounts[0].provider, count: modelCounts[0].count }) : t('noModelData')
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
                  <th>${t('provider')}</th>
                  <th>${t('model')}</th>
                  <th>${t('remainingRpm')}</th>
                  <th>${t('remainingRpd')}</th>
                  <th>${t('remainingTpm')}</th>
                  <th class="hidden-meta">${t('max')}</th>
                  <th>${t('source')}</th>
                  <th>${t('status')}</th>
                  <th>${t('lastObserved')}</th>
                  <th>${t('test')}</th>
                </tr>
              </thead>
              <tbody>${rowsHtml || `<tr><td colspan="10" class="empty">${t('emptyGroup')}</td></tr>`}</tbody>
            </table>
          </div>
        </section>
      `;
    }

    function validatedGroupSection(rowsHtml, meta) {
      return `
        <section>
          <h2 class="group-title">${t('validatedLlm')}</h2>
          <p class="group-sub">${t('validatedSub', { validatedAt: fmt(formatGmtPlus5(meta?.validated_at)), cacheAt: fmt(formatGmtPlus5(meta?.cache_created_at)) })}</p>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>${t('provider')}</th>
                  <th>${t('model')}</th>
                  <th>${t('answerToTest')}</th>
                  <th>${t('lastValidation')}</th>
                  <th>${t('test')}</th>
                </tr>
              </thead>
              <tbody>${rowsHtml || `<tr><td colspan="5" class="empty">${t('noValidated')}</td></tr>`}</tbody>
            </table>
          </div>
        </section>
      `;
    }

    function resourceKey(item) {
      const provider = String(item?.provider || '').trim().toLowerCase();
      const model = String(item?.id || item?.model_id || '').trim();
      if (!provider || !model) return '';
      return `${provider}::${model}`;
    }

    function localResourceUnionCount(localModels, validatedModels) {
      const combined = [
        ...(localModels || []),
        ...(validatedModels || []),
      ];
      const seen = new Set();
      combined.forEach((item) => {
        const key = resourceKey(item);
        if (key) seen.add(key);
      });
      return seen.size;
    }

    function rerenderFromCache() {
      if (lastDashboardData) {
        const { health, models, estimates, dispatcherCache } = lastDashboardData;
        const routeIndex = Object.fromEntries(
          (dispatcherCache.routes || []).map((route) => [`${route.provider || 'unknown'}::${route.model_id || 'unknown'}`, route])
        );
        const localResourceCount = localResourceUnionCount(
          models.data || [],
          (lastValidatedLlmPayload || {}).data || [],
        );
        const invalidResourcesCount = (dispatcherCache.invalid_resources?.data || []).length;
        const grouped = { llm: [], audio: [], video: [], other: [] };
        const previousTrendState = getTrendState();
        overviewStats.innerHTML = [
          statCard(t('service'), health.status),
          statCard(t('providers'), health.providers_count),
          modelsStatCard(localResourceCount, models.meta?.total_before_filter, invalidResourcesCount),
          statCard(t('lastProbe'), formatGmtPlus5(health.startup_probe?.last_probe_at), `${t('successful')}: ${fmt(health.startup_probe?.summary?.successful?.length || 0)}`)
        ].join('');
        (models.data || []).forEach((model) => {
          const liveItem = (health.limits || {})[model.provider] || {};
          const estimate = (estimates.providers || {})[model.provider] || {};
          if (!isOkStatus(liveItem, estimate)) return;
          const key = trendKey(model);
          grouped[categoryForModel(model)].push(rowHtml(model, liveItem, estimate, { direction: previousTrendState[key]?.direction || '', highlightClass: '' }, routeIndex[key] || {}));
        });
        groupedTables.innerHTML = [
          groupSection(t('llmTitle'), t('llmSub'), grouped.llm.join('')),
          groupSection(t('audioTitle'), t('audioSub'), grouped.audio.join('')),
          groupSection(t('videoTitle'), t('videoSub'), grouped.video.join('')),
          groupSection(t('otherTitle'), t('otherSub'), grouped.other.join('')),
        ].join('');
        recommendationsNode.innerHTML = buildRecommendations(health, models);
      }
      if (lastValidatedLlmPayload) {
        const rows = (lastValidatedLlmPayload.data || []).map((model) => validatedRowHtml(model)).join('');
        validatedLlmNode.innerHTML = validatedGroupSection(rows, lastValidatedLlmPayload.meta || {});
      }
      if (lastDispatcherStatusPayload) {
        renderDispatcherStatus(lastDispatcherStatusPayload);
      }
      if (lastDashboardData?.dispatcherCache) {
        invalidResourcesNode.innerHTML = invalidResourcesSection(lastDashboardData.dispatcherCache.invalid_resources?.data || []);
      }
    }

    function renderValidatedLlmProgress(job) {
      const total = Number(job?.total_models || 0);
      const requestsStarted = Number(job?.requests_started || 0);
      const responsesReceived = Number(job?.responses_received || 0);
      const requestsPercent = percent(requestsStarted, total);
      const responsesPercent = percent(responsesReceived, total);
      const startedAt = job?.last_started_at ? Date.parse(job.last_started_at) : NaN;
      const elapsedSeconds = Number.isNaN(startedAt) ? 0 : Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
      const statusText = job?.running
        ? `Идет ручная проверка: ${elapsedSeconds} сек`
        : job?.status === 'completed'
          ? `Ручная проверка завершена за ${elapsedSeconds} сек`
          : job?.status === 'failed'
            ? `Проверка завершилась с ошибкой через ${elapsedSeconds} сек`
            : 'Статус проверки неизвестен';

      if (!job?.running && !job?.last_started_at) {
        validatedLlmState.style.display = 'none';
        validatedLlmState.innerHTML = '';
        return;
      }

      validatedLlmState.style.display = 'block';
      validatedLlmState.innerHTML = `
          <div><strong>${statusText}</strong></div>
          <div class="progress-stack">
            <div class="progress-line">
              <div class="progress-meta">
                <span>${t('requestsToTest')}</span>
                <span>${requestsStarted} / ${total} (${requestsPercent}%)</span>
            </div>
            <div class="progress-track"><div class="progress-fill" style="width:${requestsPercent}%"></div></div>
          </div>
            <div class="progress-line">
              <div class="progress-meta">
                <span>${t('receivedResponses')}</span>
                <span>${responsesReceived} / ${total} (${responsesPercent}%)</span>
              </div>
              <div class="progress-track"><div class="progress-fill" style="width:${responsesPercent}%"></div></div>
            </div>
            <div class="sub">${t('status')}: ${fmt(job?.status)}. ${t('successful')}: ${fmt(job?.passed)}. ${t('didNotPass')}: ${fmt(job?.failed)}. Ответов: ${responsesReceived} из ${total}.</div>
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
      }, 1000);
    }

    async function loadValidatedLlmBlock() {
      try {
        const [payload, job] = await Promise.all([
          getJson('/admin/models/validated-llm'),
          getValidatedLlmJobStatus()
        ]);
        lastValidatedLlmPayload = payload;
        const rows = (payload.data || []).map((model) => validatedRowHtml(model)).join('');
        validatedLlmNode.innerHTML = validatedGroupSection(rows, payload.meta || {});
        renderValidatedLlmProgress(job);
        if (job?.running) {
          startValidatedLlmProgressPolling();
        } else if ((!payload.data || payload.data.length === 0) && !job?.running && !job?.last_started_at) {
          await refreshValidatedLlm('auto');
          return;
        }
        applyLanguage();
        localiseRenderedContent();
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

    async function loadDispatcherStatus() {
      try {
        const payload = await getJson('/admin/dispatcher/status');
        renderDispatcherStatus(payload);
      } catch (error) {
        activeProxySessionsNode.innerHTML = `<div class="status-error">${error.message}</div>`;
        proxySessionHistoryNode.innerHTML = `<div class="status-error">${error.message}</div>`;
      }
    }

    async function loadDashboard() {
      loadingState.style.display = 'block';
      groupedTables.innerHTML = '';
      recommendationsNode.innerHTML = recommendationCard(t('analyzing'), t('analyzingText'));
      validatedLlmNode.innerHTML = '';
      try {
        const [health, models, estimates, dispatcherCache, validatedPayload] = await Promise.all([
          getJson('/health/limits'),
          getJson('/admin/models/available'),
          getJson('/admin/limits/estimated'),
          getJson('/admin/dispatcher/cache'),
          getJson('/admin/models/validated-llm'),
        ]);
        lastValidatedLlmPayload = validatedPayload;
        lastDashboardData = { health, models, estimates, dispatcherCache };
        const routeIndex = Object.fromEntries(
          (dispatcherCache.routes || []).map((route) => [`${route.provider || 'unknown'}::${route.model_id || 'unknown'}`, route])
        );
        const previousTrendState = getTrendState();
        const nextTrendState = {};

        const localResourceCount = localResourceUnionCount(
          models.data || [],
          (validatedPayload || {}).data || [],
        );
        const invalidResourcesCount = (dispatcherCache.invalid_resources?.data || []).length;
        overviewStats.innerHTML = [
          statCard(t('service'), health.status),
          statCard(t('providers'), health.providers_count),
          modelsStatCard(localResourceCount, models.meta?.total_before_filter, invalidResourcesCount),
          statCard(t('lastProbe'), formatGmtPlus5(health.startup_probe?.last_probe_at), `${t('successful')}: ${fmt(health.startup_probe?.summary?.successful?.length || 0)}`)
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
            routeItem: routeIndex[key] || {},
            trendInfo: { direction, highlightClass },
            weight: resourceWeight(model, liveItem),
          });
        });
        preparedRows.sort(compareModelsByPriority);
        preparedRows.forEach((item) => {
          grouped[item.category].push(rowHtml(item.model, item.liveItem, item.estimate, item.trendInfo, item.routeItem));
        });
        setTrendState(nextTrendState);

        groupedTables.innerHTML = [
          groupSection(t('llmTitle'), t('llmSub'), grouped.llm.join('')),
          groupSection(t('audioTitle'), t('audioSub'), grouped.audio.join('')),
          groupSection(t('videoTitle'), t('videoSub'), grouped.video.join('')),
          groupSection(t('otherTitle'), t('otherSub'), grouped.other.join('')),
        ].join('');
        recommendationsNode.innerHTML = buildRecommendations(health, models);
        invalidResourcesNode.innerHTML = invalidResourcesSection(dispatcherCache.invalid_resources?.data || []);
        await loadValidatedLlmBlock();
        await loadDispatcherStatus();
        loadingState.style.display = 'none';
        applyLanguage();

        wireProviderTests();
      } catch (error) {
        overviewStats.innerHTML = [
          statCard(t('service'), 'failed'),
          statCard(t('statusError'), error.message)
        ].join('');
        groupedTables.innerHTML = `<div class="status-error">${error.message}</div>`;
        recommendationsNode.innerHTML = recommendationCard(t('failed'), error.message);
        validatedLlmNode.innerHTML = `<div class="status-error">${error.message}</div>`;
        invalidResourcesNode.innerHTML = `<div class="status-error">${error.message}</div>`;
        loadingState.style.display = 'none';
      }
    }

    let liveLimitsPollHandle = null;

    async function getLiveLimitsStatus() {
      return getJson('/health/limits/live/status');
    }

    function stopLiveLimitsPolling() {
      if (liveLimitsPollHandle) {
        clearInterval(liveLimitsPollHandle);
        liveLimitsPollHandle = null;
      }
    }

    function startLiveLimitsPolling() {
      stopLiveLimitsPolling();
      liveLimitsPollHandle = setInterval(async () => {
        try {
          const status = await getLiveLimitsStatus();
          const refreshLiveButton = document.getElementById('refreshLive');
          if (refreshLiveButton) {
            refreshLiveButton.disabled = Boolean(status.running);
            refreshLiveButton.textContent = status.running ? `${t('refreshLive')}...` : t('refreshLive');
          }
          if (!status.running) {
            stopLiveLimitsPolling();
            await loadDashboard();
          }
        } catch (_) {
          stopLiveLimitsPolling();
        }
      }, 2000);
    }

    async function refreshLive() {
      const refreshLiveButton = document.getElementById('refreshLive');
      if (refreshLiveButton) {
        refreshLiveButton.disabled = true;
        refreshLiveButton.textContent = `${t('refreshLive')}...`;
      }
      await getJson('/health/limits/live?started_by=admin_ui', { method: 'POST' });
      startLiveLimitsPolling();
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
      if (resultNode) resultNode.textContent = t('checking');
      try {
        const url = `/admin/test?provider_name=${encodeURIComponent(provider)}&model_id=${encodeURIComponent(model)}`;
        const payload = await getJson(url, { method: 'POST' });
        if (resultNode) resultNode.textContent = `${payload.model}: ${payload.message_excerpt || 'ok'}`;
        await loadDashboard();
      } catch (error) {
        if (resultNode) resultNode.textContent = error.message;
        await loadDashboard();
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
      const minutes = Number(refreshInterval.value || 10);
      autoRefreshHandle = setInterval(loadDashboard, minutes * 60 * 1000);
    }

    document.getElementById('refreshAll').addEventListener('click', loadDashboard);
    document.getElementById('refreshLive').addEventListener('click', refreshLive);
    document.getElementById('refreshValidatedLlm').addEventListener('click', refreshValidatedLlm);
    refreshInterval.addEventListener('change', startAutoRefresh);
    ensureLanguageControl();
    applyLanguage();
    if (languageSelect) {
      languageSelect.addEventListener('change', () => {
        localStorage.setItem(languageStorageKey, languageSelect.value);
        rerenderFromCache();
        applyLanguage();
        localiseRenderedContent();
      });
    }
    if (applyProxyModeButton) {
      applyProxyModeButton.addEventListener('click', async () => {
        try {
          await getJson(`/admin/dispatcher/mode?mode=${encodeURIComponent(proxyModeSelect.value)}`, { method: 'POST' });
          await loadDispatcherStatus();
        } catch (error) {
          alert(`Ошибка установки режима: ${error.message}`);
        }
      });
    }
    getLiveLimitsStatus().then((status) => {
      if (status && status.running) startLiveLimitsPolling();
    }).catch(() => {});
    loadDashboard();
    startAutoRefresh();
  </script>
</body>
</html>
"""
