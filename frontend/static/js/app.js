// 缠论分析系统 - 前端主逻辑
const API = '';

// ---- 状态 ----
let state = {
    currentCode: null,
    currentName: null,
    currentMarket: 'A',
    currentPeriod: 'K_DAY',
    watchlist: [],
    analysisData: null,
};

// ---- 图表实例 ----
let mainChart = null;
let macdChart = null;
let candleSeries = null;
let biSeries = null;
let segSeries = null;
let macdHistSeries = null;
let macdDifSeries = null;
let macdDeaSeries = null;
let bspMarkers = [];

// 中枢矩形 (用额外的 line series 模拟)
let zsRectSeries = [];

// ---- 初始化 ----
document.addEventListener('DOMContentLoaded', () => {
    initPeriodSelector();
    initSearch();
    initToggles();
    loadWatchlist();
    initCharts();
});

// ---- 周期选择器 ----
function initPeriodSelector() {
    const periods = [
        { value: 'K_5M', label: '5F' },
        { value: 'K_15M', label: '15F' },
        { value: 'K_30M', label: '30F' },
        { value: 'K_60M', label: '60F' },
        { value: 'K_DAY', label: '日' },
        { value: 'K_WEEK', label: '周' },
        { value: 'K_MON', label: '月' },
    ];
    const container = document.getElementById('periodSelector');
    periods.forEach(p => {
        const btn = document.createElement('button');
        btn.className = 'period-btn' + (p.value === state.currentPeriod ? ' active' : '');
        btn.textContent = p.label;
        btn.dataset.period = p.value;
        btn.onclick = () => selectPeriod(p.value);
        container.appendChild(btn);
    });
}

function selectPeriod(period) {
    state.currentPeriod = period;
    document.querySelectorAll('.period-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.period === period);
    });
    if (state.currentCode) {
        loadAnalysis();
    }
}

// ---- 搜索 ----
let searchTimer = null;
function initSearch() {
    const input = document.getElementById('searchInput');
    const results = document.getElementById('searchResults');

    input.addEventListener('input', () => {
        clearTimeout(searchTimer);
        const q = input.value.trim();
        if (q.length === 0) { results.classList.add('hidden'); return; }
        searchTimer = setTimeout(() => doSearch(q), 300);
    });

    input.addEventListener('blur', () => {
        setTimeout(() => results.classList.add('hidden'), 200);
    });

    input.addEventListener('focus', () => {
        if (results.children.length > 0) results.classList.remove('hidden');
    });
}

async function doSearch(q) {
    const res = await fetch(`${API}/api/search?q=${encodeURIComponent(q)}`);
    const json = await res.json();
    const container = document.getElementById('searchResults');
    container.innerHTML = '';
    if (json.ok && json.data.length > 0) {
        json.data.forEach(s => {
            const div = document.createElement('div');
            div.className = 'search-item';
            div.innerHTML = `
                <span><span class="code">${s.code}</span> <span class="name">${s.name}</span></span>
                <button class="add-btn" data-code="${s.code}" data-name="${s.name}" data-market="${s.market}">+ 自选</button>
            `;
            div.querySelector('.add-btn').onclick = (e) => {
                e.stopPropagation();
                addToWatchlist(s.code, s.name, s.market);
            };
            div.onclick = () => selectStock(s.code, s.name, s.market);
            container.appendChild(div);
        });
        container.classList.remove('hidden');
    } else {
        container.classList.add('hidden');
    }
}

// ---- 自选股 ----
async function loadWatchlist() {
    const res = await fetch(`${API}/api/watchlist`);
    const json = await res.json();
    if (json.ok) {
        state.watchlist = json.data;
        renderWatchlist();
    }
}

function renderWatchlist() {
    const container = document.getElementById('watchlist');
    container.innerHTML = '';
    state.watchlist.forEach(s => {
        const div = document.createElement('div');
        div.className = 'watchlist-item' + (s.code === state.currentCode ? ' active' : '');
        div.innerHTML = `
            <div class="info">
                <span class="stock-code">${s.code}</span>
                <span class="stock-name">${s.name}</span>
            </div>
            <button class="remove-btn" title="移除">&times;</button>
        `;
        div.querySelector('.remove-btn').onclick = (e) => {
            e.stopPropagation();
            removeFromWatchlist(s.code);
        };
        div.onclick = () => selectStock(s.code, s.name, s.market);
        container.appendChild(div);
    });
}

async function addToWatchlist(code, name, market) {
    const res = await fetch(`${API}/api/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, name, market }),
    });
    const json = await res.json();
    if (json.ok) {
        state.watchlist = json.data;
        renderWatchlist();
    }
}

async function removeFromWatchlist(code) {
    const res = await fetch(`${API}/api/watchlist/${code}`, { method: 'DELETE' });
    const json = await res.json();
    if (json.ok) {
        state.watchlist = json.data;
        renderWatchlist();
    }
}

// ---- 选择股票 ----
function selectStock(code, name, market) {
    state.currentCode = code;
    state.currentName = name;
    state.currentMarket = market || 'A';
    document.getElementById('stockTitle').textContent = `${code} ${name}`;
    document.getElementById('searchResults').classList.add('hidden');
    document.getElementById('searchInput').value = '';
    renderWatchlist();
    loadAnalysis();
}

// ---- 加载分析 ----
async function loadAnalysis() {
    const loading = document.getElementById('loading');
    loading.classList.remove('hidden');

    try {
        const url = `${API}/api/analysis/${state.currentCode}?period=${state.currentPeriod}&market=${state.currentMarket}`;
        const res = await fetch(url);
        const json = await res.json();
        if (json.ok) {
            state.analysisData = json.data;
            renderCharts();
        } else {
            alert('分析失败: ' + json.error);
        }
    } catch (e) {
        alert('请求失败: ' + e.message);
    } finally {
        loading.classList.add('hidden');
    }
}

// ---- 图表 ----
function initCharts() {
    const chartEl = document.getElementById('chart');
    const macdEl = document.getElementById('macdChart');

    const commonOptions = {
        layout: {
            background: { color: '#1a1a2e' },
            textColor: '#8892a4',
        },
        grid: {
            vertLines: { color: '#2a3a5c22' },
            horzLines: { color: '#2a3a5c22' },
        },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        timeScale: {
            timeVisible: true,
            secondsVisible: false,
            borderColor: '#2a3a5c',
        },
        rightPriceScale: { borderColor: '#2a3a5c' },
    };

    mainChart = LightweightCharts.createChart(chartEl, {
        ...commonOptions,
        width: chartEl.clientWidth,
        height: chartEl.clientHeight,
    });

    macdChart = LightweightCharts.createChart(macdEl, {
        ...commonOptions,
        width: macdEl.clientWidth,
        height: macdEl.clientHeight,
    });

    // 同步时间轴
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) macdChart.timeScale().setVisibleLogicalRange(range);
    });
    macdChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) mainChart.timeScale().setVisibleLogicalRange(range);
    });

    // 响应窗口大小变化
    const ro = new ResizeObserver(() => {
        mainChart.applyOptions({ width: chartEl.clientWidth, height: chartEl.clientHeight });
        macdChart.applyOptions({ width: macdEl.clientWidth, height: macdEl.clientHeight });
    });
    ro.observe(chartEl);
    ro.observe(macdEl);
}

function renderCharts() {
    if (!state.analysisData || !mainChart) return;
    const data = state.analysisData;

    // 清理旧 series
    mainChart.priceScale('right').applyOptions({});
    clearAllSeries();

    // 1. K线
    candleSeries = mainChart.addCandlestickSeries({
        upColor: '#ef5350',
        downColor: '#26a69a',
        wickUpColor: '#ef5350',
        wickDownColor: '#26a69a',
        borderUpColor: '#ef5350',
        borderDownColor: '#26a69a',
    });
    candleSeries.setData(data.klines);

    // 2. 笔
    drawBi(data);

    // 3. 线段
    drawSeg(data);

    // 4. 中枢
    drawZS(data);

    // 5. 买卖点
    drawBSP(data);

    // 6. MACD
    drawMACD(data);

    mainChart.timeScale().fitContent();
    macdChart.timeScale().fitContent();
}

function clearAllSeries() {
    // 移除主图上所有 series 再重建
    if (mainChart) {
        // remove all series by recreating
        const chartEl = document.getElementById('chart');
        const macdEl = document.getElementById('macdChart');
        mainChart.remove();
        macdChart.remove();
        initCharts();
    }
}

// ---- 绘制笔 ----
function drawBi(data) {
    if (!document.getElementById('toggleBi').checked) return;
    if (!data.bi_list || data.bi_list.length === 0) return;

    const points = [];
    data.bi_list.forEach(bi => {
        points.push({ time: bi.begin_time, value: bi.begin_val });
        points.push({ time: bi.end_time, value: bi.end_val });
    });

    // 去重（相邻笔首尾共享端点）
    const deduped = [points[0]];
    for (let i = 1; i < points.length; i++) {
        if (points[i].time !== points[i - 1].time || points[i].value !== points[i - 1].value) {
            deduped.push(points[i]);
        }
    }

    biSeries = mainChart.addLineSeries({
        color: '#FF8C00',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Solid,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });
    biSeries.setData(deduped);
}

// ---- 绘制线段 ----
function drawSeg(data) {
    if (!document.getElementById('toggleSeg').checked) return;
    if (!data.seg_list || data.seg_list.length === 0) return;

    const points = [];
    data.seg_list.forEach(seg => {
        points.push({ time: seg.begin_time, value: seg.begin_val });
        points.push({ time: seg.end_time, value: seg.end_val });
    });

    const deduped = [points[0]];
    for (let i = 1; i < points.length; i++) {
        if (points[i].time !== points[i - 1].time || points[i].value !== points[i - 1].value) {
            deduped.push(points[i]);
        }
    }

    segSeries = mainChart.addLineSeries({
        color: '#4FC3F7',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });
    segSeries.setData(deduped);
}

// ---- 绘制中枢 ----
function drawZS(data) {
    if (!document.getElementById('toggleZS').checked) return;
    if (!data.zs_list || data.zs_list.length === 0) return;

    // 用 area series 模拟矩形（上下边界）
    data.zs_list.forEach(zs => {
        // 为每个中枢创建一个 area series 来表示区域
        const areaSeries = mainChart.addAreaSeries({
            topColor: 'rgba(255, 165, 0, 0.12)',
            bottomColor: 'rgba(255, 165, 0, 0.03)',
            lineColor: 'rgba(255, 165, 0, 0.4)',
            lineWidth: 1,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });

        // 构造中枢的上边界数据
        const klines = data.klines;
        const areaData = [];
        for (const kl of klines) {
            if (kl.time >= zs.begin_time && kl.time <= zs.end_time) {
                areaData.push({ time: kl.time, value: zs.high });
            }
        }
        if (areaData.length > 0) {
            areaSeries.setData(areaData);
        }

        // 下边界线
        const lineSeries = mainChart.addLineSeries({
            color: 'rgba(255, 165, 0, 0.4)',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });
        const lineData = [];
        for (const kl of klines) {
            if (kl.time >= zs.begin_time && kl.time <= zs.end_time) {
                lineData.push({ time: kl.time, value: zs.low });
            }
        }
        if (lineData.length > 0) {
            lineSeries.setData(lineData);
        }

        zsRectSeries.push(areaSeries, lineSeries);
    });
}

// ---- 绘制买卖点 ----
function drawBSP(data) {
    if (!document.getElementById('toggleBSP').checked) return;
    const allBsp = [...(data.bsp_list || []), ...(data.seg_bsp_list || [])];
    if (allBsp.length === 0 || !candleSeries) return;

    const markers = allBsp.map(bsp => ({
        time: bsp.time,
        position: bsp.is_buy ? 'belowBar' : 'aboveBar',
        color: bsp.is_buy ? '#ef5350' : '#26a69a',
        shape: bsp.is_buy ? 'arrowUp' : 'arrowDown',
        text: (bsp.is_buy ? 'B' : 'S') + bsp.type + (bsp.is_seg ? 's' : ''),
    }));

    // 按时间排序
    markers.sort((a, b) => a.time - b.time);
    candleSeries.setMarkers(markers);
}

// ---- 绘制 MACD ----
function drawMACD(data) {
    if (!data.macd_list || data.macd_list.length === 0) return;

    // MACD 柱状图
    macdHistSeries = macdChart.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: false,
        priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    });
    macdHistSeries.setData(data.macd_list.map(m => ({
        time: m.time,
        value: m.macd,
        color: m.macd >= 0 ? 'rgba(239, 83, 80, 0.7)' : 'rgba(38, 166, 154, 0.7)',
    })));

    // DIF 线
    macdDifSeries = macdChart.addLineSeries({
        color: '#4FC3F7',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });
    macdDifSeries.setData(data.macd_list.map(m => ({ time: m.time, value: m.dif })));

    // DEA 线
    macdDeaSeries = macdChart.addLineSeries({
        color: '#FFB74D',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });
    macdDeaSeries.setData(data.macd_list.map(m => ({ time: m.time, value: m.dea })));
}

// ---- 显示/隐藏 开关 ----
function initToggles() {
    ['toggleBi', 'toggleSeg', 'toggleZS', 'toggleBSP'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            if (state.analysisData) renderCharts();
        });
    });
}
