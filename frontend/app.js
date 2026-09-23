"use strict";

// Integration map only. No API requests are made in this standalone prototype.
const API_ENDPOINTS = Object.freeze({
  upload: { method: "POST", path: "/api/upload" },
  calculate: { method: "POST", path: "/api/calculate" },
  recommendations: { method: "GET", path: "/api/recommendations" },
  chat: { method: "POST", path: "/api/chat" },
  export: { method: "GET", path: "/api/export" },
});

// Fixed fixtures, not a forecasting or procurement calculation algorithm.
const MOCK_PRODUCTS = [
  { sku: "TEST-001", name: "Кабель силовой", supplier: "ИЭК", stock: 50, incoming_in_period: 40, forecast_demand: 180, safety_stock: 30, recommended_qty: 120, unit: "шт", urgency: "high", reason: "Остатка и ожидаемой поставки недостаточно для покрытия прогнозируемого спроса.", warnings: [] },
  { sku: "TEST-002", name: "Автоматический выключатель C16", supplier: "Schneider Electric", stock: 24, incoming_in_period: 20, forecast_demand: 100, safety_stock: 14, recommended_qty: 70, unit: "шт", urgency: "high", reason: "Запас выключателей необходимо пополнить для покрытия ожидаемого спроса.", warnings: ["Уточните срок доставки у поставщика."] },
  { sku: "TEST-003", name: "Контактор 25 А", supplier: "ABB", stock: 12, incoming_in_period: 0, forecast_demand: 42, safety_stock: 10, recommended_qty: 40, unit: "шт", urgency: "high", reason: "Текущий запас ограничен, подтверждённых поставок в периоде нет.", warnings: ["Нет подтверждённых поступлений в плановом периоде."] },
  { sku: "TEST-004", name: "Розетка с заземлением", supplier: "EKF", stock: 80, incoming_in_period: 40, forecast_demand: 150, safety_stock: 20, recommended_qty: 50, unit: "шт", urgency: "medium", reason: "Плановое пополнение позволит сохранить страховой запас.", warnings: [] },
  { sku: "TEST-005", name: "Щит распределительный", supplier: "ИЭК", stock: 15, incoming_in_period: 10, forecast_demand: 40, safety_stock: 5, recommended_qty: 20, unit: "шт", urgency: "medium", reason: "Ожидаемые поступления покрывают только часть плановой потребности.", warnings: [] },
  { sku: "TEST-006", name: "УЗО 40 А / 30 мА", supplier: "Schneider Electric", stock: 30, incoming_in_period: 10, forecast_demand: 45, safety_stock: 10, recommended_qty: 15, unit: "шт", urgency: "low", reason: "Рекомендуется небольшое плановое пополнение для поддержания резерва.", warnings: [] },
  { sku: "TEST-007", name: "Клемма соединительная", supplier: "ABB", stock: 300, incoming_in_period: 50, forecast_demand: 200, safety_stock: 50, recommended_qty: 0, unit: "шт", urgency: "low", reason: "Остаток и ожидаемая поставка покрывают спрос и страховой запас. Дополнительный заказ не требуется.", warnings: [] },
  { sku: "TEST-008", name: "DIN-рейка 35 мм", supplier: "EKF", stock: 120, incoming_in_period: 0, forecast_demand: 80, safety_stock: 20, recommended_qty: 0, unit: "шт", urgency: "low", reason: "Текущего остатка достаточно для покрытия плановой потребности.", warnings: [] },
];

// Centralized interface and fixture translations. The product contract stays unchanged.
const translations = {
  ru: {
    brandTagline: "Умное управление запасами и закупками", brandShortTagline: "Умное управление запасами", workspace: "Рабочее пространство", headerEyebrow: "Обзор рабочего пространства",
    aiAnalysis: "AI-анализ", aiAnalysisDescription: "Прогнозируйте спрос и формируйте заказ на основе данных.",
    totalHint: "Товаров в рекомендациях", orderHint: "Для пополнения запасов", urgentHint: "Требуют вашего внимания", suppliersHint: "В вашем ассортименте",
    stepUpload: "Загрузите данные", stepReview: "Изучите рекомендации", stepExport: "Скачайте заказ",
    stepUploadHint: "Excel с данными склада", stepReviewHint: "Приоритеты и объём закупки", stepExportHint: "Готовый файл для работы",
    uploadDescription: "Добавьте Excel-файл, чтобы начать работу с рекомендациями.", uploadedDescription: "Рекомендации готовы. Замените файл, чтобы начать заново.", dropHint: "или выберите файл на устройстве", dropActive: "Отпустите файл для загрузки",
    analysisTitle: "Готовим рекомендации", analysisNote: "Деморежим: используем тестовые данные. Содержимое файла не считывается.",
    calculateReady: "✓ Рекомендации готовы", uploadExcel: "Загрузить Excel", recommendationsDescription: "План закупки с понятными приоритетами и объяснениями.",
    guideEyebrow: "От данных к решению", guideTitle: "Ваш следующий заказ — под контролем", guideDescription: "Три простых шага для уверенных решений о закупках.",
    guideDataTitle: "Начните с данных", guideDataText: "Выберите Excel-файл с данными склада.", guideReviewTitle: "Увидьте главное", guideReviewText: "Изучите приоритеты и причины рекомендаций.", guideOrderTitle: "Подготовьте заказ", guideOrderText: "Отфильтруйте товары и скачайте готовый CSV.",
    welcomeTitle: "Спросите меня о запасах и закупках", welcomeDescription: "Помогу разобраться в рекомендациях и приоритетах заказа.", quickStock: "Какие товары скоро закончатся?", quickMonth: "Что нужно заказать в этом месяце?",
    remove: "Удалить", action: "Действие", forecastShort: "Прогноз", fileBytes: "Б", fileKB: "КБ", fileMB: "МБ",
    dataReadyTitle: "Данные готовы к расчёту", dataReadyText: "Нажмите «Рассчитать рекомендации», чтобы увидеть демонстрационный план закупки.",
    skip: "К содержимому", navigation: "Основная навигация", overview: "Обзор", upload: "Загрузка данных",
    recommendations: "Рекомендации", assistant: "AI Ассистент", collapse: "Свернуть меню", expand: "Развернуть меню",
    title: "Управление закупками", subtitle: "Контролируйте запасы, прогнозируйте спрос и формируйте закупки на основе данных.", ready: "Система готова",
    statistics: "Статистика закупок", total: "Всего товаров", toOrder: "Требуют заказа", urgent: "Срочные позиции", suppliers: "Поставщиков",
    workflow: "Этапы работы", data: "Данные", exportStep: "Экспорт", uploadTitle: "Начните с данных", uploadedTitle: "Данные загружены",
    demo: "Деморежим", dropTitle: "Перетащите Excel-файл", formats: "XLSX или XLS", chooseFile: "Выбрать файл", replaceFile: "Заменить файл",
    removeFile: "Удалить выбранный файл", fileReady: "✓ Файл готов к расчёту", fileProcessed: "✓ Расчёт завершён",
    calculate: "Рассчитать рекомендации", calculating: "Анализируем данные…", calculationDone: "Расчёт завершён", calculationError: "Не удалось выполнить расчёт. Попробуйте ещё раз.",
    demoAbout: "Как работает демоверсия", demoNote: "Файл остаётся на вашем устройстве. Содержимое не считывается; рекомендации и ответы AI используют тестовые данные.",
    download: "Скачать заказ", searchLabel: "Поиск по SKU, товару или поставщику", search: "Поиск по SKU, товару или поставщику…",
    supplier: "Поставщик", allSuppliers: "Все поставщики", urgency: "Срочность", allUrgencies: "Любая срочность",
    high: "Высокая", medium: "Средняя", low: "Низкая", reset: "Сбросить", tableRegion: "Таблица рекомендаций с горизонтальной прокруткой",
    tableCaption: "Рекомендации по тестовым данным", product: "Товар", stock: "Остаток", recommended: "Рекомендовано", details: "Подробнее", detailsFor: "Подробнее: {name}",
    emptyTitle: "Данные ещё не загружены", emptyText: "Загрузите Excel, чтобы перейти от данных к плану закупки.", noResults: "Ничего не найдено", noResultsText: "Измените запрос или сбросьте фильтры.",
    loadingTitle: "Готовим рекомендации…", loadingText: "Это займёт несколько секунд.", summary: "Показано {count} из {total} · К заказу: {orders}", exportHint: "CSV · с учётом фильтров",
    askAI: "Спросить AI", assistantTitle: "QOR AI", assistantSubtitle: "Ваш помощник по запасам и закупкам", close: "Закрыть",
    chatHistory: "История сообщений", quickWhy: "Почему рекомендуется этот заказ?", quickUrgent: "Покажи срочные позиции", quickProduct: "Объясни TEST-001",
    question: "Вопрос ассистенту", chatPlaceholder: "Спросите о рекомендациях…", send: "Отправить", chatNote: "Mock AI · ответы по тестовым данным",
    greeting: "Здравствуйте! Помогу разобраться в рекомендациях. Загрузите Excel-файл и выполните расчёт, чтобы начать.",
    greetingReady: "Рекомендации готовы. Укажите SKU товара или выберите быстрый вопрос — объясню, что и почему нужно заказать.",
    you: "Вы", aiName: "QOR AI · демо", thinking: "Готовлю объяснение…", needData: "Сначала загрузите Excel-файл и выполните расчёт. Затем я смогу объяснить рекомендации.",
    changedData: "Данные изменились. Задайте вопрос повторно после расчёта.", chatError: "Не удалось подготовить ответ. Отправьте вопрос ещё раз.",
    chatProduct: "{name} ({sku})\n\nПрогноз спроса — {forecast} {unit}, остаток — {stock} {unit}, в пути — {incoming} {unit}, страховой запас — {safety} {unit}.",
    chatOrder: "Рекомендуется заказать {quantity} {unit}.", chatNoOrder: "Заказ не требуется: рекомендовано 0.", chatUrgent: "В первую очередь проверьте эти позиции:",
    chatNoUrgent: "Позиций с высокой срочностью нет.", chatUrgentItem: "• {sku} — {name}: {quantity} {unit}, {supplier}.",
    chatUrgentEnd: "Уточните сроки поставки перед заказом.", chatFallback: "Укажите SKU или полное название товара — я объясню рекомендацию. Также могу показать срочные позиции.",
    chatOverview: "К заказу: {orders} из {total} позиций. Высокий приоритет: {urgent}. Рекомендации учитывают прогноз спроса, остаток, поставки и страховой запас. Укажите SKU для подробного объяснения.",
    productDetails: "Карточка товара", incoming: "В пути", forecast: "Прогноз спроса", safety: "Страховой запас", reasonTitle: "Почему рекомендуется этот заказ?",
    baseExplanation: "Объяснение базовой потребности", baseNeed: "Базовая потребность", negativeNeed: "Запаса достаточно — дополнительный заказ не нужен.",
    businessRules: "Итоговый заказ может учитывать минимальную партию и другие условия закупки.", warnings: "Предупреждения", noWarnings: "Предупреждений нет.", unit: "шт", unitHeader: "Единица",
    exportQuantity: "Рекомендованное количество", fileSelected: "Файл выбран", fileRemoved: "Файл удалён", selectFirst: "Выберите Excel-файл", invalidFormat: "Неверный формат. Выберите XLSX или XLS.", oneFile: "Выберите один Excel-файл", noExport: "Нет данных для экспорта", exportDone: "Заказ сформирован: {count} позиций", exportError: "Не удалось скачать заказ. Попробуйте ещё раз.",
    products: [
      ["Кабель силовой", "Остатка и ожидаемой поставки недостаточно для покрытия прогнозируемого спроса."],
      ["Автоматический выключатель C16", "Запас выключателей необходимо пополнить для покрытия ожидаемого спроса.", "Уточните срок доставки у поставщика."],
      ["Контактор 25 А", "Текущий запас ограничен, подтверждённых поставок в периоде нет.", "Нет подтверждённых поступлений в плановом периоде."],
      ["Розетка с заземлением", "Плановое пополнение позволит сохранить страховой запас."],
      ["Щит распределительный", "Ожидаемые поступления покрывают только часть плановой потребности."],
      ["УЗО 40 А / 30 мА", "Рекомендуется небольшое плановое пополнение для поддержания резерва."],
      ["Клемма соединительная", "Остаток и ожидаемая поставка покрывают спрос и страховой запас. Дополнительный заказ не требуется."],
      ["DIN-рейка 35 мм", "Текущего остатка достаточно для покрытия плановой потребности."]
    ]
  },
  kz: {
    brandTagline: "Қорлар мен сатып алуды ақылды басқару", brandShortTagline: "Қорларды ақылды басқару", workspace: "Жұмыс кеңістігі", headerEyebrow: "Жұмыс кеңістігіне шолу",
    aiAnalysis: "AI талдау", aiAnalysisDescription: "Сұранысты болжап, деректер негізінде тапсырыс жасаңыз.",
    totalHint: "Ұсынымдардағы тауарлар", orderHint: "Қорды толықтыру үшін", urgentHint: "Назар аударуды қажет етеді", suppliersHint: "Ассортиментіңізде",
    stepUpload: "Деректерді жүктеңіз", stepReview: "Ұсынымдарды зерттеңіз", stepExport: "Тапсырысты жүктеп алыңыз",
    stepUploadHint: "Қойма деректері бар Excel", stepReviewHint: "Басымдықтар мен тапсырыс көлемі", stepExportHint: "Жұмысқа дайын файл",
    uploadDescription: "Ұсынымдармен жұмысты бастау үшін Excel файлын қосыңыз.", uploadedDescription: "Ұсынымдар дайын. Қайта бастау үшін файлды ауыстырыңыз.", dropHint: "немесе құрылғыдан файл таңдаңыз", dropActive: "Жүктеу үшін файлды жіберіңіз",
    analysisTitle: "Ұсынымдар дайындалып жатыр", analysisNote: "Демо режим: сынақ деректері қолданылады. Файл мазмұны оқылмайды.",
    calculateReady: "✓ Ұсынымдар дайын", uploadExcel: "Excel жүктеу", recommendationsDescription: "Басымдықтары мен түсіндірмелері анық сатып алу жоспары.",
    guideEyebrow: "Деректерден шешімге", guideTitle: "Келесі тапсырысыңыз бақылауда", guideDescription: "Сатып алу туралы сенімді шешімдерге арналған үш қадам.",
    guideDataTitle: "Деректерден бастаңыз", guideDataText: "Қойма деректері бар Excel файлын таңдаңыз.", guideReviewTitle: "Маңыздысын көріңіз", guideReviewText: "Басымдықтар мен ұсынымдардың себептерін зерттеңіз.", guideOrderTitle: "Тапсырысты дайындаңыз", guideOrderText: "Тауарларды сүзіп, дайын CSV файлын жүктеп алыңыз.",
    welcomeTitle: "Қорлар мен сатып алу туралы сұраңыз", welcomeDescription: "Ұсынымдар мен тапсырыс басымдықтарын түсінуге көмектесемін.", quickStock: "Қандай тауарлар жақында таусылады?", quickMonth: "Осы айда не тапсырыс беру керек?",
    remove: "Жою", action: "Әрекет", forecastShort: "Болжам", fileBytes: "Б", fileKB: "КБ", fileMB: "МБ",
    dataReadyTitle: "Деректер есептеуге дайын", dataReadyText: "Демо сатып алу жоспарын көру үшін «Ұсынымдарды есептеу» түймесін басыңыз.",
    skip: "Мазмұнға өту", navigation: "Негізгі мәзір", overview: "Шолу", upload: "Деректерді жүктеу",
    recommendations: "Ұсынымдар", assistant: "AI көмекші", collapse: "Мәзірді жинау", expand: "Мәзірді ашу",
    title: "Сатып алуды басқару", subtitle: "Қорларды бақылаңыз, сұранысты болжаңыз және деректер негізінде сатып алуды жоспарлаңыз.", ready: "Жүйе дайын",
    statistics: "Сатып алу статистикасы", total: "Барлық тауар", toOrder: "Тапсырыс қажет", urgent: "Шұғыл тауарлар", suppliers: "Жеткізушілер",
    workflow: "Жұмыс кезеңдері", data: "Деректер", exportStep: "Экспорт", uploadTitle: "Деректерден бастаңыз", uploadedTitle: "Деректер жүктелді",
    demo: "Демо режим", dropTitle: "Excel файлын осында сүйреңіз", formats: "XLSX немесе XLS", chooseFile: "Файлды таңдау", replaceFile: "Файлды ауыстыру",
    removeFile: "Таңдалған файлды жою", fileReady: "✓ Файл есептеуге дайын", fileProcessed: "✓ Есептеу аяқталды",
    calculate: "Ұсынымдарды есептеу", calculating: "Деректер талданып жатыр…", calculationDone: "Есептеу аяқталды", calculationError: "Есептеу орындалмады. Қайталап көріңіз.",
    demoAbout: "Демо нұсқа қалай жұмыс істейді", demoNote: "Файл құрылғыңызда қалады. Оның мазмұны оқылмайды; ұсынымдар мен AI жауаптары сынақ деректеріне негізделген.",
    download: "Тапсырысты жүктеп алу", searchLabel: "SKU, тауар немесе жеткізуші бойынша іздеу", search: "SKU, тауар немесе жеткізуші бойынша іздеу…",
    supplier: "Жеткізуші", allSuppliers: "Барлық жеткізуші", urgency: "Шұғылдық", allUrgencies: "Барлық деңгей",
    high: "Жоғары", medium: "Орташа", low: "Төмен", reset: "Тазарту", tableRegion: "Көлденең айналдыруға болатын ұсынымдар кестесі",
    tableCaption: "Сынақ деректері бойынша ұсынымдар", product: "Тауар", stock: "Қалдық", recommended: "Ұсынылған саны", details: "Толығырақ", detailsFor: "Толығырақ: {name}",
    emptyTitle: "Деректер әлі жүктелмеген", emptyText: "Сатып алу жоспарын дайындау үшін Excel файлын жүктеңіз.", noResults: "Ештеңе табылмады", noResultsText: "Іздеу шарттарын өзгертіңіз немесе сүзгілерді тазалаңыз.",
    loadingTitle: "Ұсынымдар дайындалып жатыр…", loadingText: "Бұл бірнеше секунд алады.", summary: "{total} тауардың {count} көрсетілді · Тапсырыс қажет: {orders}", exportHint: "CSV · сүзгілер ескеріледі",
    askAI: "AI-дан сұрау", assistantTitle: "QOR AI", assistantSubtitle: "Қорлар мен сатып алу бойынша көмекшіңіз", close: "Жабу",
    chatHistory: "Хабарламалар тарихы", quickWhy: "Бұл тапсырыс неге ұсынылады?", quickUrgent: "Шұғыл тауарларды көрсет", quickProduct: "TEST-001 туралы түсіндір",
    question: "Көмекшіге сұрақ", chatPlaceholder: "Ұсынымдар туралы сұраңыз…", send: "Жіберу", chatNote: "Mock AI · сынақ деректері бойынша жауаптар",
    greeting: "Сәлеметсіз бе! Ұсынымдарды түсінуге көмектесемін. Бастау үшін Excel файлын жүктеп, есептеуді орындаңыз.",
    greetingReady: "Ұсынымдар дайын. Тауардың SKU кодын жазыңыз немесе дайын сұрақты таңдаңыз — нені және не үшін тапсырыс беру керегін түсіндіремін.",
    you: "Сіз", aiName: "QOR AI · демо", thinking: "Түсіндірме дайындалып жатыр…", needData: "Алдымен Excel файлын жүктеп, есептеуді орындаңыз. Содан кейін ұсынымдарды түсіндіре аламын.",
    changedData: "Деректер өзгерді. Есептеуден кейін сұрақты қайта қойыңыз.", chatError: "Жауап дайындалмады. Сұрақты қайта жіберіңіз.",
    chatProduct: "{name} ({sku})\n\nСұраныс болжамы — {forecast} {unit}, қалдық — {stock} {unit}, жолда — {incoming} {unit}, сақтандыру қоры — {safety} {unit}.",
    chatOrder: "{quantity} {unit} тапсырыс беру ұсынылады.", chatNoOrder: "Тапсырыс қажет емес: ұсынылған саны — 0.", chatUrgent: "Алдымен мына тауарларды тексеріңіз:",
    chatNoUrgent: "Шұғылдығы жоғары тауарлар жоқ.", chatUrgentItem: "• {sku} — {name}: {quantity} {unit}, {supplier}.",
    chatUrgentEnd: "Тапсырыс бермес бұрын жеткізу мерзімін нақтылаңыз.", chatFallback: "SKU немесе тауардың толық атауын жазыңыз — ұсынымды түсіндіремін. Шұғыл тауарларды да көрсете аламын.",
    chatOverview: "{total} тауардың {orders} үшін тапсырыс қажет. Жоғары басымдық: {urgent}. Ұсынымдар сұраныс болжамын, қалдықты, жеткізілімдерді және сақтандыру қорын ескереді. Толық түсіндірме үшін SKU көрсетіңіз.",
    productDetails: "Тауар карточкасы", incoming: "Жолда", forecast: "Сұраныс болжамы", safety: "Сақтандыру қоры", reasonTitle: "Бұл тапсырыс неге ұсынылады?",
    baseExplanation: "Базалық қажеттіліктің түсіндірмесі", baseNeed: "Базалық қажеттілік", negativeNeed: "Қор жеткілікті — қосымша тапсырыс қажет емес.",
    businessRules: "Соңғы тапсырыста ең аз партия көлемі және басқа сатып алу шарттары ескерілуі мүмкін.", warnings: "Ескертулер", noWarnings: "Ескертулер жоқ.", unit: "дана", unitHeader: "Өлшем бірлігі",
    exportQuantity: "Ұсынылған саны", fileSelected: "Файл таңдалды", fileRemoved: "Файл жойылды", selectFirst: "Excel файлын таңдаңыз", invalidFormat: "Формат қате. XLSX немесе XLS таңдаңыз.", oneFile: "Бір Excel файлын таңдаңыз", noExport: "Экспортқа деректер жоқ", exportDone: "Тапсырыс дайын: {count} тауар", exportError: "Тапсырысты жүктеп алу мүмкін болмады. Қайталап көріңіз.",
    products: [
      ["Күштік кабель", "Қалдық пен күтілетін жеткізілім болжанған сұранысты өтеуге жеткіліксіз."],
      ["C16 автоматты ажыратқышы", "Күтілетін сұранысты өтеу үшін ажыратқыштар қорын толықтыру қажет.", "Жеткізу мерзімін жеткізушіден нақтылаңыз."],
      ["25 А контакторы", "Қазіргі қор аз, осы кезеңде расталған жеткізілімдер жоқ.", "Жоспарлы кезеңге расталған жеткізілімдер жоқ."],
      ["Жерге тұйықталған розетка", "Жоспарлы толықтыру сақтандыру қорын сақтауға мүмкіндік береді."],
      ["Тарату қалқаны", "Күтілетін жеткізілімдер жоспарлы қажеттіліктің бір бөлігін ғана өтейді."],
      ["40 А / 30 мА қорғаныш ажыратқышы", "Резервті сақтау үшін қорды аздап толықтыру ұсынылады."],
      ["Жалғау клеммасы", "Қалдық пен күтілетін жеткізілім сұранысты және сақтандыру қорын өтейді. Қосымша тапсырыс қажет емес."],
      ["35 мм DIN рейкасы", "Қазіргі қалдық жоспарлы қажеттілікті өтеуге жеткілікті."]
    ]
  },
  en: {
    brandTagline: "Smart inventory and procurement management", brandShortTagline: "Smart inventory management", workspace: "Workspace", headerEyebrow: "Workspace overview",
    aiAnalysis: "AI analysis", aiAnalysisDescription: "Forecast demand and prepare orders based on your data.",
    totalHint: "Products in recommendations", orderHint: "To replenish inventory", urgentHint: "Need your attention", suppliersHint: "Across your inventory",
    stepUpload: "Upload your data", stepReview: "Review recommendations", stepExport: "Download your order",
    stepUploadHint: "Excel inventory data", stepReviewHint: "Priorities and order quantities", stepExportHint: "A file ready to use",
    uploadDescription: "Add an Excel file to start working with recommendations.", uploadedDescription: "Recommendations are ready. Replace the file to start again.", dropHint: "or choose a file on your device", dropActive: "Release to upload your file",
    analysisTitle: "Preparing recommendations", analysisNote: "Demo mode: using sample data. Your file contents are not read.",
    calculateReady: "✓ Recommendations ready", uploadExcel: "Upload Excel", recommendationsDescription: "A procurement plan with clear priorities and explanations.",
    guideEyebrow: "From data to decisions", guideTitle: "Your next order, under control", guideDescription: "Three simple steps to confident procurement decisions.",
    guideDataTitle: "Start with your data", guideDataText: "Choose an Excel file with inventory data.", guideReviewTitle: "See what matters", guideReviewText: "Review priorities and the reasons behind each recommendation.", guideOrderTitle: "Prepare your order", guideOrderText: "Filter products and download a ready-to-use CSV.",
    welcomeTitle: "Ask me about inventory and procurement", welcomeDescription: "I can help explain recommendations and order priorities.", quickStock: "Which products are running low?", quickMonth: "What should I order this month?",
    remove: "Remove", action: "Action", forecastShort: "Forecast", fileBytes: "B", fileKB: "KB", fileMB: "MB",
    dataReadyTitle: "Your data is ready", dataReadyText: "Select Calculate recommendations to see a demo procurement plan.",
    skip: "Skip to content", navigation: "Main navigation", overview: "Overview", upload: "Upload data",
    recommendations: "Recommendations", assistant: "AI Assistant", collapse: "Collapse menu", expand: "Expand menu",
    title: "Procurement management", subtitle: "Track inventory, forecast demand and plan procurement based on your data.", ready: "System ready",
    statistics: "Procurement summary", total: "Total products", toOrder: "Require ordering", urgent: "Urgent items", suppliers: "Suppliers",
    workflow: "Workflow", data: "Data", exportStep: "Export", uploadTitle: "Start with your data", uploadedTitle: "Data uploaded",
    demo: "Demo mode", dropTitle: "Drop your Excel file here", formats: "XLSX or XLS", chooseFile: "Choose file", replaceFile: "Replace file",
    removeFile: "Remove selected file", fileReady: "✓ Ready to calculate", fileProcessed: "✓ Calculation complete",
    calculate: "Calculate recommendations", calculating: "Analyzing data…", calculationDone: "Calculation complete", calculationError: "Calculation failed. Please try again.",
    demoAbout: "How this demo works", demoNote: "Your file stays on your device. Its contents are not read; recommendations and AI responses use sample data.",
    download: "Download order", searchLabel: "Search by SKU, product or supplier", search: "Search by SKU, product or supplier…",
    supplier: "Supplier", allSuppliers: "All suppliers", urgency: "Urgency", allUrgencies: "All priorities",
    high: "High", medium: "Medium", low: "Low", reset: "Reset", tableRegion: "Recommendations table, scroll horizontally",
    tableCaption: "Recommendations based on sample data", product: "Product", stock: "On hand", recommended: "Recommended", details: "Details", detailsFor: "Details: {name}",
    emptyTitle: "No data uploaded yet", emptyText: "Upload Excel to turn your data into a procurement plan.", noResults: "No matching products", noResultsText: "Try a different search or reset your filters.",
    loadingTitle: "Preparing recommendations…", loadingText: "This will only take a few seconds.", summary: "Showing {count} of {total} · To order: {orders}", exportHint: "CSV · active filters applied",
    askAI: "Ask AI", assistantTitle: "QOR AI", assistantSubtitle: "Your inventory and procurement assistant", close: "Close",
    chatHistory: "Message history", quickWhy: "Why is this order recommended?", quickUrgent: "Show urgent items", quickProduct: "Explain TEST-001",
    question: "Question for the assistant", chatPlaceholder: "Ask about recommendations…", send: "Send", chatNote: "Mock AI · responses based on sample data",
    greeting: "Hello! I can help explain your recommendations. Upload an Excel file and run the calculation to get started.",
    greetingReady: "Your recommendations are ready. Enter a product SKU or choose a quick question to understand what to order and why.",
    you: "You", aiName: "QOR AI · demo", thinking: "Preparing an explanation…", needData: "Upload an Excel file and run the calculation first. Then I can explain the recommendations.",
    changedData: "The dataset has changed. Please ask again after calculation.", chatError: "Could not prepare a response. Please send your question again.",
    chatProduct: "{name} ({sku})\n\nForecast demand: {forecast} {unit}; on hand: {stock} {unit}; incoming: {incoming} {unit}; safety stock: {safety} {unit}.",
    chatOrder: "Recommended order: {quantity} {unit}.", chatNoOrder: "No order required: recommended quantity is 0.", chatUrgent: "Review these high-priority items first:",
    chatNoUrgent: "There are no high-priority items.", chatUrgentItem: "• {sku} — {name}: {quantity} {unit}, {supplier}.",
    chatUrgentEnd: "Confirm delivery dates before placing the order.", chatFallback: "Enter a SKU or full product name for an explanation. I can also show urgent items.",
    chatOverview: "{orders} of {total} products require ordering. High priority: {urgent}. Recommendations reflect demand, stock on hand, incoming deliveries and safety stock. Enter a SKU for a detailed explanation.",
    productDetails: "Product details", incoming: "Incoming", forecast: "Forecast demand", safety: "Safety stock", reasonTitle: "Why is this order recommended?",
    baseExplanation: "Base requirement breakdown", baseNeed: "Base requirement", negativeNeed: "Inventory is sufficient; no additional order is needed.",
    businessRules: "The final order may reflect minimum quantities and other purchasing terms.", warnings: "Warnings", noWarnings: "No warnings.", unit: "pcs", unitHeader: "Unit",
    exportQuantity: "Recommended quantity", fileSelected: "File selected", fileRemoved: "File removed", selectFirst: "Choose an Excel file", invalidFormat: "Invalid format. Choose XLSX or XLS.", oneFile: "Choose one Excel file", noExport: "No items to export", exportDone: "Order ready: {count} items", exportError: "Could not download the order. Please try again.",
    products: [
      ["Power cable", "Stock on hand and incoming deliveries do not cover forecast demand."],
      ["C16 circuit breaker", "Replenish circuit breaker inventory to cover expected demand.", "Confirm the delivery date with the supplier."],
      ["25 A contactor", "Current stock is limited and no deliveries are confirmed for this period.", "No confirmed deliveries in the planning period."],
      ["Grounded socket", "Scheduled replenishment will maintain safety stock."],
      ["Distribution board", "Expected deliveries cover only part of the planned requirement."],
      ["40 A / 30 mA RCD", "A small scheduled replenishment is recommended to maintain the reserve."],
      ["Terminal connector", "Current stock and incoming deliveries cover demand and safety stock. No additional order is needed."],
      ["35 mm DIN rail", "Stock on hand is sufficient to cover the planned requirement."]
    ]
  }
};

const state = {
  language: "ru", file: null, products: [], calculating: false, chatting: false,
  revision: 0, status: "idle", fileError: false, exported: false,
  activeSku: null, messages: [{ role: "assistant", kind: "greeting" }],
};
let statisticsFrame;
const renderedMessages = new WeakMap();
const $ = (id) => document.getElementById(id);
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const normalize = (value) => String(value).toLocaleLowerCase().replaceAll("ё", "е").trim();
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
const t = (key, params = {}, language = state.language) => {
  const template = translations[language][key];
  if (typeof template !== "string") throw new Error(`Missing translation: ${language}.${key}`);
  return template.replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`));
};

function readPreference(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function savePreference(key, value) {
  try { localStorage.setItem(key, value); } catch { /* The UI also works without storage. */ }
}

function localizedProduct(product, language = state.language) {
  const index = MOCK_PRODUCTS.findIndex((fixture) => fixture.sku === product.sku);
  // Only translate known fixtures. Future API products keep their server text.
  const isFixture = index >= 0 && MOCK_PRODUCTS[index].name === product.name && MOCK_PRODUCTS[index].reason === product.reason;
  const copy = isFixture ? translations[language].products[index] : null;
  return {
    ...product,
    name: copy?.[0] ?? product.name,
    reason: copy?.[1] ?? product.reason,
    warnings: copy ? (copy[2] ? [copy[2]] : []) : product.warnings,
    unit: product.unit === "шт" ? t("unit", {}, language) : product.unit,
  };
}

// Replace these transport methods with /api/upload (FormData), /api/calculate,
// /api/recommendations and /api/chat. No network requests are made here.
const dataService = {
  async calculate(file) {
    if (!file) throw new Error("Missing file");
    await delay(1100);
    return MOCK_PRODUCTS.map((product) => ({ ...product, warnings: [...product.warnings] }));
  },
  async chat(question, products) {
    await delay(550);
    return getMockChatResponse(question, products);
  },
};

function setLanguage(language) {
  state.language = Object.hasOwn(translations, language) ? language : "ru";
  savePreference("zakupai.language", state.language);
  document.documentElement.lang = state.language === "kz" ? "kk" : state.language;
  document.title = `QOR.AI — ${t("title")}`;
  $("language").value = state.language;
  document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
  for (const [attribute, dataset] of [["placeholder", "i18nPlaceholder"], ["aria-label", "i18nAria"], ["title", "i18nTitle"]]) {
    document.querySelectorAll(`[data-${dataset.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}]`).forEach((node) => node.setAttribute(attribute, t(node.dataset[dataset])));
  }
  populateSupplierFilter();
  updateStatistics(false);
  renderUpload();
  renderRecommendations();
  renderChat();
  updateSidebarLabel();
  if ($("product-dialog").open && state.activeSku) renderProductDetails();
  document.querySelectorAll(".toast").forEach((toast) => {
    toast.querySelector(".toast-text").textContent = t(toast.dataset.key, JSON.parse(toast.dataset.params));
  });
}

function showNotification(key, type = "success", params = {}) {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.dataset.key = key;
  toast.dataset.params = JSON.stringify(params);
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  const icon = document.createElement("span");
  icon.className = "toast-symbol";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = type === "error" ? "!" : "✓";
  const text = document.createElement("span");
  text.className = "toast-text";
  text.textContent = t(key, params);
  toast.append(icon, text);
  $("notifications").append(toast);
  // Keep the latest result visible without stacking messages over the workspace.
  while ($("notifications").children.length > 1) $("notifications").firstElementChild.remove();
  setTimeout(() => toast.remove(), 4500);
}

function renderUpload() {
  const complete = state.status === "complete";
  $("upload").classList.toggle("is-complete", complete);
  $("upload-title").textContent = t(complete ? "uploadedTitle" : "uploadTitle");
  document.querySelector('[data-i18n="uploadDescription"]').textContent = t(complete ? "uploadedDescription" : "uploadDescription");
  $("upload-prompt").hidden = !!state.file;
  $("file-card").hidden = !state.file;
  $("drop-zone").classList.toggle("has-file", !!state.file);
  $("drop-zone").classList.toggle("error", state.fileError);
  $("file-name").textContent = state.file?.name ?? "";
  $("file-name").title = state.file?.name ?? "";
  if ($("file-size")) $("file-size").textContent = state.file ? formatFileSize(state.file.size) : "";
  $("file-status").textContent = state.file ? t(complete ? "fileProcessed" : "fileReady") : "";
  $("choose-file").textContent = t(state.file ? "replaceFile" : "chooseFile");
  $("upload-error").hidden = !state.fileError;
  $("upload-error").textContent = state.fileError ? t("invalidFormat") : "";
  $("calculate-label").textContent = t(state.calculating ? "calculating" : complete ? "calculateReady" : "calculate");
  $("calculate").classList.toggle("is-success", complete);
  $("calculate").setAttribute("aria-busy", String(state.calculating));
  $("calculate").querySelector(".spinner").hidden = !state.calculating;
  $("calculate").querySelector("svg")?.classList.toggle("is-hidden", state.calculating || complete);
  $("calculation-status").textContent = state.status === "error" ? t("calculationError") : "";
  if ($("analysis-state")) $("analysis-state").hidden = !state.calculating;
  $("system-status").textContent = t(state.calculating ? "calculating" : "ready");
  $("system-status").classList.toggle("is-busy", state.calculating);
  $("recommendations").setAttribute("aria-busy", String(state.calculating));
  for (const id of ["calculate", "choose-file", "remove-file", "file-input", "export"]) $(id).disabled = state.calculating;
  const stepIndex = state.exported ? 3 : complete ? 1 : 0;
  ["step-upload", "step-review", "step-export"].forEach((id, index) => {
    $(id).classList.toggle("current", index === stepIndex);
    $(id).classList.toggle("complete", index < stepIndex);
    $(id).querySelector("b").textContent = index < stepIndex ? "✓" : String(index + 1);
    if (index === stepIndex) $(id).setAttribute("aria-current", "step");
    else $(id).removeAttribute("aria-current");
  });
  renderDragState();
}

function formatFileSize(bytes) {
  const unit = bytes >= 1024 * 1024 ? "fileMB" : bytes >= 1024 ? "fileKB" : "fileBytes";
  const divisor = unit === "fileMB" ? 1024 * 1024 : unit === "fileKB" ? 1024 : 1;
  const locale = state.language === "kz" ? "kk-KZ" : state.language;
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(bytes / divisor)} ${t(unit)}`;
}

function renderDragState() {
  const active = $("drop-zone").classList.contains("drag-over");
  document.querySelector('[data-i18n="dropTitle"]').textContent = t(active ? "dropActive" : "dropTitle");
  if (state.file && active) $("file-status").textContent = t("dropActive");
}

function setDragOver(active) {
  $("drop-zone").classList.toggle("drag-over", active);
  renderDragState();
  if (!active && state.file) $("file-status").textContent = t(state.status === "complete" ? "fileProcessed" : "fileReady");
}

function resetFilters() {
  $("search").value = "";
  $("supplier-filter").value = "";
  $("urgency-filter").value = "";
  renderRecommendations();
}

function resetDataset() {
  state.revision += 1;
  state.products = [];
  state.exported = false;
  state.status = "idle";
  state.activeSku = null;
  setActiveNavigation("#upload");
  populateSupplierFilter();
  resetFilters();
  updateStatistics();
}

function handleFileSelect(file) {
  if (!file || state.calculating) return;
  resetDataset();
  state.fileError = !/\.(xlsx|xls)$/i.test(file.name);
  state.file = state.fileError ? null : file;
  $("file-input").value = ""; // Selecting the same file again must fire change.
  renderUpload();
  renderRecommendations();
  showNotification(state.fileError ? "invalidFormat" : "fileSelected", state.fileError ? "error" : "success");
}

function removeFile() {
  if (state.calculating) return;
  state.file = null;
  state.fileError = false;
  $("file-input").value = "";
  resetDataset();
  renderUpload();
  showNotification("fileRemoved");
  $("choose-file").focus();
}

async function calculateRecommendations() {
  if (state.calculating) return;
  if (!state.file) {
    showNotification("selectFirst", "error");
    $("choose-file").focus();
    return;
  }
  resetDataset();
  state.calculating = true;
  state.status = "loading";
  renderUpload();
  renderRecommendations();
  try {
    state.products = await dataService.calculate(state.file);
    state.status = "complete";
    populateSupplierFilter();
    updateStatistics();
    showNotification("calculationDone");
  } catch {
    state.status = "error";
    showNotification("calculationError", "error");
  } finally {
    state.calculating = false;
    renderUpload();
    renderRecommendations();
    if (state.status === "complete") {
      setActiveNavigation("#recommendations");
      $("recommendations").scrollIntoView({ behavior: "auto", block: "start" });
      // Move keyboard focus to the next task after results arrive.
      $("search").focus({ preventScroll: true });
    }
  }
}

function updateStatistics(animate = true) {
  cancelAnimationFrame(statisticsFrame);
  const stats = document.querySelector(".stats");
  stats.classList.toggle("is-empty", state.status !== "complete");
  const values = [
    [$("stat-total"), state.products.length],
    [$("stat-order"), state.products.filter((p) => p.recommended_qty > 0).length],
    [$("stat-urgent"), state.products.filter((p) => p.urgency === "high").length],
    [$("stat-suppliers"), new Set(state.products.map((p) => p.supplier)).size],
  ];
  stats.setAttribute("aria-busy", "false");
  if (state.status !== "complete") {
    values.forEach(([node]) => { node.textContent = "—"; });
    return;
  }
  const format = new Intl.NumberFormat(state.language === "kz" ? "kk-KZ" : state.language);
  const draw = (progress) => values.forEach(([node, value]) => { node.textContent = format.format(Math.round(value * progress)); });
  if (!animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    draw(1);
    return;
  }
  const started = performance.now();
  stats.setAttribute("aria-busy", "true");
  draw(0);
  const tick = (now) => {
    const progress = Math.min((now - started) / 300, 1);
    draw(1 - Math.pow(1 - progress, 3));
    if (progress < 1) statisticsFrame = requestAnimationFrame(tick);
    else stats.setAttribute("aria-busy", "false");
  };
  statisticsFrame = requestAnimationFrame(tick);
}

function populateSupplierFilter() {
  const select = $("supplier-filter");
  const previous = select.value;
  select.replaceChildren(new Option(t("allSuppliers"), ""));
  [...new Set(state.products.map((p) => p.supplier))].forEach((supplier) => select.add(new Option(supplier, supplier)));
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function applyFilters() {
  const query = normalize($("search").value);
  return state.products.filter((p) => {
    // Search every locale so switching language doesn't invalidate a query.
    const names = Object.keys(translations).map((language) => localizedProduct(p, language).name);
    return (!$("supplier-filter").value || p.supplier === $("supplier-filter").value) &&
      (!$("urgency-filter").value || p.urgency === $("urgency-filter").value) &&
      (!query || [p.sku, p.name, p.supplier, ...names].some((value) => normalize(value).includes(query)));
  });
}

function urgencyBadge(urgency) {
  const level = ["high", "medium", "low"].includes(urgency) ? urgency : "low";
  return `<span class="badge ${level}"><span aria-hidden="true">${{ high: "↑", medium: "–", low: "↓" }[level]}</span>${t(level)}</span>`;
}

function renderRecommendations() {
  const products = applyFilters();
  const hasData = state.products.length > 0;
  $("recommendation-rows").innerHTML = products.map((raw) => {
    const p = localizedProduct(raw);
    return `<tr><td class="product-name">${escapeHTML(p.name)}</td><td class="sku-value">${escapeHTML(p.sku)}</td><td class="supplier-name">${escapeHTML(p.supplier)}</td>
      <td class="numeric">${p.stock}<span class="unit">${escapeHTML(p.unit)}</span></td>
      <td class="numeric">${p.incoming_in_period}<span class="unit">${escapeHTML(p.unit)}</span></td>
      <td class="numeric">${p.forecast_demand}<span class="unit">${escapeHTML(p.unit)}</span></td>
      <td class="numeric"><span class="${p.recommended_qty > 0 ? "quantity" : ""}">${p.recommended_qty}</span><span class="unit">${escapeHTML(p.unit)}</span></td>
      <td>${urgencyBadge(p.urgency)}</td><td><button class="details-button" type="button" data-sku="${escapeHTML(p.sku)}" aria-label="${escapeHTML(t("detailsFor", { name: p.name }))}">${t("details")} <span aria-hidden="true">↗</span></button></td></tr>`;
  }).join("");
  for (const id of ["filters", "export", "result-count", "table-footer"]) $(id).hidden = !hasData;
  $("table-scroll").hidden = !products.length;
  $("result-count").textContent = products.length;
  $("empty-state").hidden = products.length > 0 || state.calculating;
  $("empty-state").querySelector("h3").textContent = t(hasData ? "noResults" : state.file ? "dataReadyTitle" : "emptyTitle");
  $("empty-state").querySelector("p").textContent = t(hasData ? "noResultsText" : state.file ? "dataReadyText" : "emptyText");
  if ($("empty-upload")) {
    $("empty-upload").hidden = state.calculating;
    $("empty-upload").querySelector("span").textContent = t(hasData ? "reset" : state.file ? "calculate" : "uploadExcel");
    $("empty-upload").querySelector("use")?.setAttribute("href", hasData ? "#i-list" : state.file ? "#i-spark" : "#i-upload");
  }
  $("table-summary").textContent = t("summary", { count: products.length, total: state.products.length, orders: products.filter((p) => p.recommended_qty > 0).length });
}

function renderProductDetails() {
  const raw = state.products.find((p) => p.sku === state.activeSku);
  if (!raw) return;
  const p = localizedProduct(raw);
  const metrics = [["stock", p.stock], ["incoming", p.incoming_in_period], ["forecast", p.forecast_demand], ["safety", p.safety_stock], ["recommended", p.recommended_qty]];
  // Explanatory arithmetic only. Never generates or changes recommended_qty.
  const baseNeed = p.forecast_demand + p.safety_stock - p.stock - p.incoming_in_period;
  const formula = [["forecast", p.forecast_demand, ""], ["safety", p.safety_stock, "+"], ["stock", p.stock, "−"], ["incoming", p.incoming_in_period, "−"], ["baseNeed", baseNeed, "="]];
  $("product-details").innerHTML = `<h2 id="product-title">${escapeHTML(p.name)}</h2>
    <p class="product-subtitle">${escapeHTML(p.sku)} · ${escapeHTML(p.supplier)}</p>${urgencyBadge(p.urgency)}
    <dl class="detail-grid">${metrics.map(([label, value]) => `<div><dt>${t(label)}</dt><dd>${value} <span class="unit">${escapeHTML(p.unit)}</span></dd></div>`).join("")}</dl>
    <h3>${t("reasonTitle")}</h3><p class="detail-copy">${escapeHTML(p.reason)}</p>
    <div class="explanation"><h3>${t("baseExplanation")}</h3><dl class="formula-rows">${formula.map(([label, value, sign]) => `<div${label === "baseNeed" ? ' class="formula-total"' : ""}><dt>${sign} ${t(label)}</dt><dd>${value} ${escapeHTML(p.unit)}</dd></div>`).join("")}</dl>
    <dl class="recommended-total"><div><dt>${t("recommended")}</dt><dd>${p.recommended_qty} <span>${escapeHTML(p.unit)}</span></dd></div></dl>
    ${baseNeed < 0 ? `<p>${t("negativeNeed")}</p>` : ""}<p>${t("businessRules")}</p></div>
    <h3>${t("warnings")}</h3>${p.warnings.length ? `<ul class="warnings">${p.warnings.map((warning) => `<li>${escapeHTML(warning)}</li>`).join("")}</ul>` : `<p class="detail-copy">${t("noWarnings")}</p>`}`;
}

function openProductDetails(sku) {
  if (!state.products.some((p) => p.sku === sku)) return;
  state.activeSku = sku;
  renderProductDetails();
  $("product-dialog").showModal();
}

// Structured mock replies can be re-rendered on language changes. User text is
// kept verbatim; product snapshots preserve the historical recommendation.
function getMockChatResponse(question, products) {
  if (!products.length) return { kind: "needData" };
  const query = normalize(question);
  const product = products.find((p) => query.includes(normalize(p.sku)) ||
    Object.keys(translations).some((language) => query.includes(normalize(localizedProduct(p, language).name))));
  if (product) return { kind: "product", product };
  const isPrompt = (key) => Object.keys(translations).some((language) => query === normalize(t(key, {}, language)));
  // Quick prompts reuse the existing demo summaries; no stockout dates or
  // calendar-specific forecasts are inferred from the fixture values.
  if (isPrompt("quickStock") || /сроч|приоритет|шұғыл|басым|urgent|priorit/.test(query)) return { kind: "urgent", products: products.filter((p) => p.urgency === "high") };
  if (isPrompt("quickWhy") || isPrompt("quickMonth") || /^(почему такой заказ|неге осындай тапсырыс|why this order)\??$/.test(query)) return { kind: "overview", products };
  return { kind: "chatFallback" };
}

function chatMessageText(message) {
  if (message.role === "user") return message.text;
  if (message.kind === "greeting") return t(state.products.length ? "greetingReady" : "greeting");
  if (message.kind === "product") {
    const p = localizedProduct(message.product);
    return `${t("chatProduct", { name: p.name, sku: p.sku, forecast: p.forecast_demand, stock: p.stock, incoming: p.incoming_in_period, safety: p.safety_stock, unit: p.unit })}\n\n${p.recommended_qty > 0 ? t("chatOrder", { quantity: p.recommended_qty, unit: p.unit }) : t("chatNoOrder")} ${p.reason}${p.warnings.length ? `\n\n${t("warnings")}: ${p.warnings.join(" ")}` : ""}`;
  }
  if (message.kind === "urgent") {
    if (!message.products.length) return t("chatNoUrgent");
    return `${t("chatUrgent")}\n${message.products.map((raw) => {
      const p = localizedProduct(raw);
      return t("chatUrgentItem", { ...p, quantity: p.recommended_qty });
    }).join("\n")}\n\n${t("chatUrgentEnd")}`;
  }
  if (message.kind === "overview") return t("chatOverview", { total: message.products.length, orders: message.products.filter((p) => p.recommended_qty > 0).length, urgent: message.products.filter((p) => p.urgency === "high").length });
  return t(message.kind);
}

function renderChat() {
  const log = $("chat-messages");
  const welcome = $("chat-welcome");
  if (welcome) welcome.hidden = state.messages.some((message) => message.role === "user");
  log.replaceChildren();
  state.messages.forEach((message) => {
    if (welcome && message.kind === "greeting") return;
    const node = document.createElement("div");
    node.className = `message ${message.role}`;
    const label = document.createElement("span");
    label.className = "message-label";
    label.textContent = t(message.role === "user" ? "you" : "aiName");
    const content = document.createElement("p");
    content.textContent = chatMessageText(message);
    node.classList.toggle("is-new", renderedMessages.get(message) !== content.textContent);
    node.classList.toggle("is-thinking", message.kind === "thinking");
    renderedMessages.set(message, content.textContent);
    node.append(label, content);
    log.append(node);
  });
  log.scrollTop = log.scrollHeight;
  log.setAttribute("aria-busy", String(state.chatting));
  $("send-chat").disabled = state.chatting;
  document.querySelectorAll("[data-question]").forEach((button) => { button.disabled = state.chatting; });
}

async function sendChatMessage(event) {
  event?.preventDefault();
  const question = $("chat-input").value.trim();
  if (!question || state.chatting) return;
  state.chatting = true;
  const revision = state.revision;
  state.messages.push({ role: "user", text: question });
  const pending = { role: "assistant", kind: "thinking" };
  state.messages.push(pending);
  $("chat-input").value = "";
  renderChat();
  try {
    const response = await dataService.chat(question, state.products);
    Object.assign(pending, revision === state.revision ? response : { kind: "changedData" });
  } catch {
    pending.kind = "chatError";
  } finally {
    state.chatting = false;
    renderChat();
  }
}

function openAssistant() {
  renderChat();
  if (!$("assistant").open) $("assistant").showModal();
  $("chat-input").focus();
}

function csvCell(value) {
  let text = String(value);
  if (/^\s*[=+@-]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function buildOrderCSV(products) {
  const rows = [["SKU", t("product"), t("supplier"), t("exportQuantity"), t("unitHeader"), t("urgency")], ...products.map((raw) => {
    const p = localizedProduct(raw);
    return [p.sku, p.name, p.supplier, p.recommended_qty, p.unit, t(p.urgency)];
  })];
  // UTF-8 BOM for Excel; quote fields and preserve Cyrillic / Kazakh text.
  return "\uFEFF" + rows.map((row) => row.map(csvCell).join(";")).join("\r\n");
}

function exportOrder() {
  const products = applyFilters().filter((p) => p.recommended_qty > 0);
  if (!products.length) return showNotification("noExport", "error");
  // Future GET /api/export must receive the same active filter parameters.
  let url;
  let link;
  try {
    url = URL.createObjectURL(new Blob([buildOrderCSV(products)], { type: "text/csv;charset=utf-8;" }));
    link = document.createElement("a");
    link.href = url;
    link.download = "qorai_order.csv";
    document.body.append(link);
    link.click();
    state.exported = true;
    renderUpload();
    showNotification("exportDone", "success", { count: products.length });
  } catch {
    showNotification("exportError", "error");
  } finally {
    link?.remove();
    if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

function setActiveNavigation(hash) {
  document.querySelectorAll(".nav-link[href]").forEach((link) => {
    const active = link.getAttribute("href") === hash;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}
function updateSidebarLabel() {
  const collapsed = document.body.classList.contains("sidebar-collapsed");
  $("sidebar-toggle").setAttribute("aria-expanded", String(!collapsed));
  $("sidebar-toggle").setAttribute("aria-label", t(collapsed ? "expand" : "collapse"));
  $("sidebar-toggle").title = t(collapsed ? "expand" : "collapse");
}

// Native dialogs provide focus trapping, Escape and focus restoration.
$("language").addEventListener("change", (event) => setLanguage(event.target.value));
$("sidebar-toggle").addEventListener("click", () => {
  document.body.classList.toggle("sidebar-collapsed");
  savePreference("zakupai.sidebarCollapsed", String(document.body.classList.contains("sidebar-collapsed")));
  updateSidebarLabel();
});
$("choose-file").addEventListener("click", () => $("file-input").click());
$("empty-upload")?.addEventListener("click", () => {
  if (state.products.length) {
    resetFilters();
    $("search").focus({ preventScroll: true });
    return;
  }
  if (state.file) return calculateRecommendations();
  setActiveNavigation("#upload");
  $("upload").scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  $("file-input").click();
});
$("remove-file").addEventListener("click", removeFile);
$("file-input").addEventListener("change", (event) => handleFileSelect(event.target.files[0]));
for (const name of ["dragenter", "dragover"]) $("drop-zone").addEventListener(name, (event) => {
  event.preventDefault();
  if (!state.calculating) setDragOver(true);
});
$("drop-zone").addEventListener("dragleave", (event) => {
  if (!$("drop-zone").contains(event.relatedTarget)) setDragOver(false);
});
$("drop-zone").addEventListener("drop", (event) => {
  event.preventDefault();
  setDragOver(false);
  if (state.calculating) return;
  if (event.dataTransfer.files.length !== 1) return showNotification("oneFile", "error");
  handleFileSelect(event.dataTransfer.files[0]);
});
for (const name of ["dragover", "drop"]) document.addEventListener(name, (event) => {
  if ([...event.dataTransfer.types].includes("Files")) event.preventDefault();
});
$("calculate").addEventListener("click", calculateRecommendations);
$("export").addEventListener("click", exportOrder);
$("search").addEventListener("input", renderRecommendations);
$("supplier-filter").addEventListener("change", renderRecommendations);
$("urgency-filter").addEventListener("change", renderRecommendations);
$("reset-filters").addEventListener("click", resetFilters);
$("recommendation-rows").addEventListener("click", (event) => {
  const button = event.target.closest("[data-sku]");
  if (button) openProductDetails(button.dataset.sku);
});
$("close-dialog").addEventListener("click", () => $("product-dialog").close());
$("close-assistant").addEventListener("click", () => $("assistant").close());
for (const id of ["product-dialog", "assistant"]) $(id).addEventListener("click", (event) => {
  const rect = $(id).getBoundingClientRect();
  if (event.target === $(id) && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) $(id).close();
});
$("product-ask").addEventListener("click", () => {
  const sku = state.activeSku;
  $("product-dialog").close();
  openAssistant();
  $("chat-input").value = sku;
  sendChatMessage();
});
$("open-assistant").addEventListener("click", openAssistant);
$("nav-assistant").addEventListener("click", openAssistant);
$("chat-form").addEventListener("submit", sendChatMessage);
$("chat-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && event.isComposing) event.preventDefault();
});
document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => {
  const key = { stock: "quickStock", month: "quickMonth", why: "quickWhy", urgent: "quickUrgent", product: "quickProduct" }[button.dataset.question];
  $("chat-input").value = t(key);
  sendChatMessage();
  $("chat-input").focus();
}));
document.querySelectorAll(".nav-link[href]").forEach((link) => link.addEventListener("click", () => setActiveNavigation(link.getAttribute("href"))));
$("assistant").addEventListener("close", () => $("nav-assistant").classList.remove("active"));
$("assistant").addEventListener("toggle", () => $("nav-assistant").classList.toggle("active", $("assistant").open));

if (readPreference("zakupai.sidebarCollapsed") === "true") document.body.classList.add("sidebar-collapsed");
updateStatistics();
setLanguage(readPreference("zakupai.language") || "ru");
