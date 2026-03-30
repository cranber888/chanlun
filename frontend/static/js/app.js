// 缠论分析系统 - 前端主逻辑
const API = '';

// MA 均线颜色
const MA_COLORS = {
    '5': '#FFD700',
    '10': '#FF69B4',
    '20': '#00BFFF',
    '60': '#9370DB',
};

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
let volumeChart = null;
let macdChart = null;
let candleSeries = null;

// ---- 自动刷新 ----
let autoRefreshTimer = null;
const AUTO_REFRESH_INTERVAL = 30000; // 30秒

// ---- 初始化 ----
document.addEventListener('DOMContentLoaded', () => {
    initPeriodSelector();
    initSearch();
    initToggles();
    initBiSettings();
    initRefresh();
    initBacktest();
    loadWatchlist();
    initCharts();
    checkTradingStatus();
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
    if (state.currentCode) loadAnalysis();
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
    const container = document.getElementById('searchResults');
    container.innerHTML = '<div class="search-item"><span style="color:#8892a4">搜索中...</span></div>';
    container.classList.remove('hidden');
    const res = await fetch(`${API}/api/search?q=${encodeURIComponent(q)}`);
    const json = await res.json();
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

// ---- 笔规则配置 ----
function getBiConfig() {
    return {
        bi_strict: document.getElementById('cfgBiStrict').checked,
        bi_fx_check: document.getElementById('cfgBiFxCheck').value,
        gap_as_kl: document.getElementById('cfgGapAsKl').checked,
        bi_end_is_peak: document.getElementById('cfgBiEndIsPeak').checked,
        bi_allow_sub_peak: document.getElementById('cfgBiAllowSubPeak').checked,
    };
}

// ---- 中枢规则配置 ----
function getZsConfig() {
    return {
        zs_max_bi_cnt: parseInt(document.getElementById('cfgZsMaxBiCnt').value),
    };
}

function initBiSettings() {
    // 修改笔设置后自动重新分析
    ['cfgBiStrict', 'cfgGapAsKl', 'cfgBiEndIsPeak', 'cfgBiAllowSubPeak'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            if (state.currentCode) loadAnalysis();
        });
    });
    document.getElementById('cfgBiFxCheck').addEventListener('change', () => {
        if (state.currentCode) loadAnalysis();
    });
    // 修改中枢设置后自动重新分析
    document.getElementById('cfgZsMaxBiCnt').addEventListener('change', () => {
        if (state.currentCode) loadAnalysis();
    });
}

// ---- 刷新功能 ----
function initRefresh() {
    // 手动刷新按钮
    document.getElementById('refreshBtn').onclick = async () => {
        if (!state.currentCode) return;
        const btn = document.getElementById('refreshBtn');
        btn.classList.add('spinning');
        // 清除该股票缓存
        await fetch(`${API}/api/refresh/${state.currentCode}`, { method: 'POST' });
        await loadAnalysis();
        btn.classList.remove('spinning');
    };

    // 自动刷新开关
    document.getElementById('toggleAutoRefresh').addEventListener('change', (e) => {
        if (e.target.checked) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    });
}

function startAutoRefresh() {
    stopAutoRefresh();
    const label = document.getElementById('autoRefreshLabel');
    label.classList.add('active');
    label.textContent = '自动(30s)';
    autoRefreshTimer = setInterval(async () => {
        if (!state.currentCode) return;
        // 清除缓存后重新加载
        await fetch(`${API}/api/refresh/${state.currentCode}`, { method: 'POST' });
        await loadAnalysis();
    }, AUTO_REFRESH_INTERVAL);
}

function stopAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }
    const label = document.getElementById('autoRefreshLabel');
    label.classList.remove('active');
    label.textContent = '自动';
}

async function checkTradingStatus() {
    try {
        const res = await fetch(`${API}/api/trading_status`);
        const json = await res.json();
        if (json.ok && json.is_trading) {
            // 交易时间自动开启提示（不自动开启，让用户选择）
            document.getElementById('autoRefreshLabel').textContent = '自动(交易中)';
        }
    } catch (e) { /* 忽略 */ }
    // 每 5 分钟检查一次交易状态
    setTimeout(checkTradingStatus, 300000);
}

// ---- 加载分析 ----
async function loadAnalysis() {
    const loading = document.getElementById('loading');
    loading.classList.remove('hidden');

    try {
        const biCfg = getBiConfig();
        const zsCfg = getZsConfig();
        const params = new URLSearchParams({
            period: state.currentPeriod,
            market: state.currentMarket,
            bi_strict: biCfg.bi_strict,
            bi_fx_check: biCfg.bi_fx_check,
            gap_as_kl: biCfg.gap_as_kl,
            bi_end_is_peak: biCfg.bi_end_is_peak,
            bi_allow_sub_peak: biCfg.bi_allow_sub_peak,
            zs_max_bi_cnt: zsCfg.zs_max_bi_cnt,
        });
        const url = `${API}/api/analysis/${state.currentCode}?${params}`;
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
    const volumeEl = document.getElementById('volumeChart');
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
        localization: {
            timeFormatter: (ts) => {
                const d = new Date(ts * 1000);
                const yy = d.getFullYear();
                const mm = String(d.getMonth() + 1).padStart(2, '0');
                const dd = String(d.getDate()).padStart(2, '0');
                const hh = String(d.getHours()).padStart(2, '0');
                const mi = String(d.getMinutes()).padStart(2, '0');
                if (hh === '23' && mi === '59') return `${yy}/${mm}/${dd}`;
                return `${yy}/${mm}/${dd} ${hh}:${mi}`;
            },
        },
    };

    mainChart = LightweightCharts.createChart(chartEl, {
        ...commonOptions,
        width: chartEl.clientWidth,
        height: chartEl.clientHeight,
    });

    volumeChart = LightweightCharts.createChart(volumeEl, {
        ...commonOptions,
        width: volumeEl.clientWidth,
        height: volumeEl.clientHeight,
    });

    macdChart = LightweightCharts.createChart(macdEl, {
        ...commonOptions,
        width: macdEl.clientWidth,
        height: macdEl.clientHeight,
    });

    // 同步三个图表的时间轴
    let syncing = false;
    function syncRange(source, targets) {
        source.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (syncing || !range) return;
            syncing = true;
            targets.forEach(t => t.timeScale().setVisibleLogicalRange(range));
            syncing = false;
        });
    }
    syncRange(mainChart, [volumeChart, macdChart]);
    syncRange(volumeChart, [mainChart, macdChart]);
    syncRange(macdChart, [mainChart, volumeChart]);

    // 响应窗口大小变化
    const ro = new ResizeObserver(() => {
        mainChart.applyOptions({ width: chartEl.clientWidth, height: chartEl.clientHeight });
        volumeChart.applyOptions({ width: volumeEl.clientWidth, height: volumeEl.clientHeight });
        macdChart.applyOptions({ width: macdEl.clientWidth, height: macdEl.clientHeight });
    });
    ro.observe(chartEl);
    ro.observe(volumeEl);
    ro.observe(macdEl);
}

function renderCharts() {
    if (!state.analysisData || !mainChart) return;
    const data = state.analysisData;

    // 清理并重建图表
    clearAllSeries();

    // 1. K线（被合并的K线用黄色标记）
    candleSeries = mainChart.addCandlestickSeries({
        upColor: '#ef5350',
        downColor: '#26a69a',
        wickUpColor: '#ef5350',
        wickDownColor: '#26a69a',
        borderUpColor: '#ef5350',
        borderDownColor: '#26a69a',
    });

    const showMerge = document.getElementById('toggleMergedKL').checked;
    if (showMerge) {
        // 标记被合并的K线：用黄色边框
        const klData = data.klines.map(kl => {
            if (kl.merged) {
                return {
                    ...kl,
                    borderUpColor: '#FFD54F',
                    borderDownColor: '#FFD54F',
                    wickUpColor: '#FFD54F',
                    wickDownColor: '#FFD54F',
                };
            }
            return kl;
        });
        candleSeries.setData(klData);
    } else {
        candleSeries.setData(data.klines);
    }

    // 1.5 合并K线（显示合并后的高低范围）
    drawMergedKL(data);

    // 2. MA 均线
    drawMA(data);

    // 3. BOLL
    drawBOLL(data);

    // 4. 笔
    drawBi(data);

    // 5. 线段
    drawSeg(data);

    // 6. 中枢
    drawZS(data);

    // 7. 笔走势（紫色）
    drawBiTrend(data);

    // 8. 高级别走势（蓝色）
    drawSegSeg(data);

    // 9. 高级别中枢（绿色）
    drawSegZS(data);

    // 10. 买卖点
    drawBSP(data);

    // 11. 成交量
    drawVolume(data);

    // 12. MACD
    drawMACD(data);

    mainChart.timeScale().fitContent();
    volumeChart.timeScale().fitContent();
    macdChart.timeScale().fitContent();
}

function clearAllSeries() {
    if (mainChart) {
        mainChart.remove();
        volumeChart.remove();
        macdChart.remove();
        initCharts();
    }
}

// ---- 绘制 MA 均线 ----
function drawMA(data) {
    if (!document.getElementById('toggleMA').checked) return;
    if (!data.ma_data) return;

    for (const [period, points] of Object.entries(data.ma_data)) {
        if (points.length === 0) continue;
        const color = MA_COLORS[period] || '#AAAAAA';
        const series = mainChart.addLineSeries({
            color: color,
            lineWidth: 1,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
            title: `MA${period}`,
        });
        series.setData(points);
    }
}

// ---- 绘制 BOLL ----
function drawBOLL(data) {
    if (!document.getElementById('toggleBOLL').checked) return;
    if (!data.boll_data || data.boll_data.length === 0) return;

    // 上轨
    const upperSeries = mainChart.addLineSeries({
        color: 'rgba(255, 152, 0, 0.6)',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
        title: 'BOLL上',
    });
    upperSeries.setData(data.boll_data.map(b => ({ time: b.time, value: b.upper })));

    // 中轨
    const midSeries = mainChart.addLineSeries({
        color: 'rgba(255, 152, 0, 0.4)',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
        title: 'BOLL中',
    });
    midSeries.setData(data.boll_data.map(b => ({ time: b.time, value: b.mid })));

    // 下轨
    const lowerSeries = mainChart.addLineSeries({
        color: 'rgba(255, 152, 0, 0.6)',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
        title: 'BOLL下',
    });
    lowerSeries.setData(data.boll_data.map(b => ({ time: b.time, value: b.lower })));
}

// ---- 绘制合并K线（黄色高低范围线） ----
function drawMergedKL(data) {
    if (!document.getElementById('toggleMergedKL').checked) return;
    if (!data.merged_klines || data.merged_klines.length === 0) return;

    data.merged_klines.forEach(mk => {
        const klines = data.klines;
        // 找出该合并K线范围内的原始K线时间点
        const timePoints = [];
        for (const kl of klines) {
            if (kl.time >= mk.begin_time && kl.time <= mk.end_time) {
                timePoints.push(kl.time);
            }
        }
        if (timePoints.length < 2) return;

        // 合并后的上边界线（黄色实线）
        const highSeries = mainChart.addLineSeries({
            color: '#FFD54F',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });
        highSeries.setData(timePoints.map(t => ({ time: t, value: mk.high })));

        // 合并后的下边界线（黄色实线）
        const lowSeries = mainChart.addLineSeries({
            color: '#FFD54F',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });
        lowSeries.setData(timePoints.map(t => ({ time: t, value: mk.low })));
    });
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

    const deduped = [points[0]];
    for (let i = 1; i < points.length; i++) {
        if (points[i].time !== points[i - 1].time || points[i].value !== points[i - 1].value) {
            deduped.push(points[i]);
        }
    }

    const biSeries = mainChart.addLineSeries({
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

    const segSeries = mainChart.addLineSeries({
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

    data.zs_list.forEach(zs => {
        const areaSeries = mainChart.addAreaSeries({
            topColor: 'rgba(255, 165, 0, 0.12)',
            bottomColor: 'rgba(255, 165, 0, 0.03)',
            lineColor: 'rgba(255, 165, 0, 0.4)',
            lineWidth: 1,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });

        const klines = data.klines;
        const areaData = [];
        for (const kl of klines) {
            if (kl.time >= zs.begin_time && kl.time <= zs.end_time) {
                areaData.push({ time: kl.time, value: zs.high });
            }
        }
        if (areaData.length > 0) areaSeries.setData(areaData);

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
        if (lineData.length > 0) lineSeries.setData(lineData);
    });
}

// ---- 绘制笔走势（紫色线） ----
function drawBiTrend(data) {
    if (!document.getElementById('toggleBiTrend').checked) return;
    if (!data.bi_trend_list || data.bi_trend_list.length === 0) return;

    const points = [];
    data.bi_trend_list.forEach(t => {
        points.push({ time: t.begin_time, value: t.begin_val });
        points.push({ time: t.end_time, value: t.end_val });
    });

    // 去重（相邻走势首尾相连的点）
    const deduped = [points[0]];
    for (let i = 1; i < points.length; i++) {
        if (points[i].time !== points[i - 1].time || points[i].value !== points[i - 1].value) {
            deduped.push(points[i]);
        }
    }

    const biTrendSeries = mainChart.addLineSeries({
        color: '#AB47BC',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });
    biTrendSeries.setData(deduped);

    // 在走势转折点画圆点标记
    if (candleSeries && deduped.length > 0) {
        const markers = [];
        data.bi_trend_list.forEach(t => {
            // 标记走势类型: T=趋势, P=盘整
            const label = t.type === 'trend' ? `T${t.zs_count}` : (t.has_3b_return ? 'P3B' : 'P');
            markers.push({
                time: t.end_time,
                position: t.dir === 'up' ? 'aboveBar' : 'belowBar',
                color: '#AB47BC',
                shape: 'circle',
                text: label,
            });
        });
        // 合并到已有 markers 或单独设置
        const existingMarkers = candleSeries.markers ? candleSeries.markers() : [];
        // 买卖点 markers 已经设置过了，这里不覆盖
        // 笔走势标记通过独立 series 的 markers 实现
    }
}

// ---- 绘制高级别走势（蓝色线） ----
function drawSegSeg(data) {
    if (!document.getElementById('toggleSegSeg').checked) return;
    if (!data.segseg_list || data.segseg_list.length === 0) return;

    const points = [];
    data.segseg_list.forEach(seg => {
        points.push({ time: seg.begin_time, value: seg.begin_val });
        points.push({ time: seg.end_time, value: seg.end_val });
    });

    const deduped = [points[0]];
    for (let i = 1; i < points.length; i++) {
        if (points[i].time !== points[i - 1].time || points[i].value !== points[i - 1].value) {
            deduped.push(points[i]);
        }
    }

    const segSegSeries = mainChart.addLineSeries({
        color: '#4CAF50',
        lineWidth: 3,
        lineStyle: LightweightCharts.LineStyle.Solid,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });
    segSegSeries.setData(deduped);
}

// ---- 绘制高级别中枢（绿色框） ----
function drawSegZS(data) {
    if (!document.getElementById('toggleSegZS').checked) return;
    if (!data.seg_zs_list || data.seg_zs_list.length === 0) return;

    data.seg_zs_list.forEach(zs => {
        // 绿色填充区域（上边界）
        const areaSeries = mainChart.addAreaSeries({
            topColor: 'rgba(76, 175, 80, 0.15)',
            bottomColor: 'rgba(76, 175, 80, 0.03)',
            lineColor: 'rgba(76, 175, 80, 0.6)',
            lineWidth: 2,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });

        const klines = data.klines;
        const areaData = [];
        for (const kl of klines) {
            if (kl.time >= zs.begin_time && kl.time <= zs.end_time) {
                areaData.push({ time: kl.time, value: zs.high });
            }
        }
        if (areaData.length > 0) areaSeries.setData(areaData);

        // 绿色虚线（下边界）
        const lineSeries = mainChart.addLineSeries({
            color: 'rgba(76, 175, 80, 0.6)',
            lineWidth: 2,
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
        if (lineData.length > 0) lineSeries.setData(lineData);
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

    markers.sort((a, b) => a.time - b.time);
    candleSeries.setMarkers(markers);
}

// ---- 绘制成交量 ----
function drawVolume(data) {
    if (!data.klines || data.klines.length === 0) return;

    const volSeries = volumeChart.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: false,
        priceFormat: {
            type: 'volume',
        },
    });

    const volData = data.klines.map(kl => ({
        time: kl.time,
        value: kl.volume || 0,
        color: kl.close >= kl.open
            ? 'rgba(239, 83, 80, 0.6)'   // 红色 (涨)
            : 'rgba(38, 166, 154, 0.6)',  // 绿色 (跌)
    }));

    volSeries.setData(volData);
}

// ---- 绘制 MACD ----
function drawMACD(data) {
    if (!data.macd_list || data.macd_list.length === 0) return;

    const macdHistSeries = macdChart.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: false,
        priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    });
    macdHistSeries.setData(data.macd_list.map(m => ({
        time: m.time,
        value: m.macd,
        color: m.macd >= 0 ? 'rgba(239, 83, 80, 0.7)' : 'rgba(38, 166, 154, 0.7)',
    })));

    const macdDifSeries = macdChart.addLineSeries({
        color: '#4FC3F7',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });
    macdDifSeries.setData(data.macd_list.map(m => ({ time: m.time, value: m.dif })));

    const macdDeaSeries = macdChart.addLineSeries({
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
    ['toggleMergedKL', 'toggleBi', 'toggleSeg', 'toggleZS', 'toggleBSP', 'toggleMA', 'toggleBOLL', 'toggleBiTrend', 'toggleSegSeg', 'toggleSegZS'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            if (state.analysisData) renderCharts();
        });
    });
}

// ============================================================
// ---- 模拟回测 ----
// ============================================================

let equityChart = null;

function initBacktest() {
    document.getElementById('btnRunBacktest').onclick = runBacktest;
    document.getElementById('btnCloseBacktest').onclick = closeBacktest;
}

async function runBacktest() {
    if (!state.currentCode) {
        alert('请先选择股票');
        return;
    }

    const btn = document.getElementById('btnRunBacktest');
    btn.disabled = true;
    btn.textContent = '回测中...';

    const biCfg = getBiConfig();
    const zsCfg = getZsConfig();

    const body = {
        code: state.currentCode,
        period: state.currentPeriod,
        market: state.currentMarket,
        initial_capital: parseFloat(document.getElementById('cfgCapital').value),
        position_ratio: parseFloat(document.getElementById('cfgPosition').value),
        commission_rate: 0.001,
        stamp_tax_rate: 0.001,
        stop_loss_pct: parseFloat(document.getElementById('cfgStopLoss').value),
        buy_types: document.getElementById('cfgBuyType').value.split(','),
        sell_types: document.getElementById('cfgSellType').value.split(','),
        bi_strict: biCfg.bi_strict,
        bi_fx_check: biCfg.bi_fx_check,
        gap_as_kl: biCfg.gap_as_kl,
        bi_end_is_peak: biCfg.bi_end_is_peak,
        bi_allow_sub_peak: biCfg.bi_allow_sub_peak,
        zs_max_bi_cnt: zsCfg.zs_max_bi_cnt,
    };

    try {
        const res = await fetch(`${API}/api/backtest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const json = await res.json();
        if (json.ok) {
            showBacktestResult(json.data);
        } else {
            // 处理422验证错误和普通错误
            const errMsg = json.error || (json.detail ? JSON.stringify(json.detail) : '未知错误');
            alert('回测失败: ' + errMsg);
        }
    } catch (e) {
        alert('回测请求失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '开始回测';
    }
}

function showBacktestResult(data) {
    const panel = document.getElementById('backtestPanel');
    panel.classList.remove('hidden');

    const s = data.summary;

    // 绩效摘要
    const summaryEl = document.getElementById('backtestSummary');
    const returnClass = s.total_return >= 0 ? 'positive' : 'negative';
    const annualClass = s.annual_return >= 0 ? 'positive' : 'negative';

    summaryEl.innerHTML = `
        <div class="stat-card">
            <div class="label">总收益</div>
            <div class="value ${returnClass}">${s.total_return >= 0 ? '+' : ''}${s.total_return}%</div>
        </div>
        <div class="stat-card">
            <div class="label">年化收益</div>
            <div class="value ${annualClass}">${s.annual_return >= 0 ? '+' : ''}${s.annual_return}%</div>
        </div>
        <div class="stat-card">
            <div class="label">最大回撤</div>
            <div class="value negative">${s.max_drawdown}%</div>
        </div>
        <div class="stat-card">
            <div class="label">交易次数</div>
            <div class="value">${s.total_trades}</div>
        </div>
        <div class="stat-card">
            <div class="label">胜率</div>
            <div class="value ${s.win_rate >= 50 ? 'positive' : 'negative'}">${s.win_rate}%</div>
        </div>
        <div class="stat-card">
            <div class="label">盈亏比</div>
            <div class="value">${s.profit_loss_ratio}</div>
        </div>
        <div class="stat-card">
            <div class="label">期末资产</div>
            <div class="value ${s.final_equity >= s.initial_capital ? 'positive' : 'negative'}">${(s.final_equity / 10000).toFixed(2)}万</div>
        </div>
    `;

    // 资金曲线
    drawEquityCurve(data.equity_curve);

    // 交易记录
    drawTradesTable(data.trades);

    // 在K线图上标记交易点
    markTrades(data.trades);
}

function drawEquityCurve(curve) {
    const el = document.getElementById('backtestEquity');

    // 清理旧图表
    if (equityChart) {
        equityChart.remove();
        equityChart = null;
    }

    equityChart = LightweightCharts.createChart(el, {
        width: el.clientWidth,
        height: 120,
        layout: {
            background: { color: '#1a1a2e' },
            textColor: '#8892a4',
        },
        grid: {
            vertLines: { color: '#2a3a5c22' },
            horzLines: { color: '#2a3a5c22' },
        },
        timeScale: {
            timeVisible: true,
            secondsVisible: false,
            borderColor: '#2a3a5c',
        },
        rightPriceScale: { borderColor: '#2a3a5c' },
    });

    const series = equityChart.addAreaSeries({
        topColor: 'rgba(79, 195, 247, 0.3)',
        bottomColor: 'rgba(79, 195, 247, 0.02)',
        lineColor: '#4FC3F7',
        lineWidth: 2,
        crosshairMarkerVisible: false,
        lastValueVisible: true,
        priceLineVisible: false,
    });

    series.setData(curve.map(c => ({ time: c.time, value: c.equity })));
    equityChart.timeScale().fitContent();

    // 响应窗口大小
    const ro = new ResizeObserver(() => {
        if (equityChart) {
            equityChart.applyOptions({ width: el.clientWidth });
        }
    });
    ro.observe(el);
}

function drawTradesTable(trades) {
    const el = document.getElementById('backtestTrades');
    if (trades.length === 0) {
        el.innerHTML = '<p style="color:var(--text-secondary);font-size:13px;padding:8px;">无交易记录</p>';
        return;
    }

    const formatTime = (ts) => {
        const d = new Date(ts * 1000);
        const yy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        const hh = String(d.getHours()).padStart(2, '0');
        const mi = String(d.getMinutes()).padStart(2, '0');
        if (hh === '23' && mi === '59') return `${yy}/${mm}/${dd}`;
        return `${yy}/${mm}/${dd} ${hh}:${mi}`;
    };

    const reasonMap = { signal: '信号', stop_loss: '止损', end: '结束' };

    let html = `<h4>交易记录 (${trades.length}笔)</h4>
    <table class="trades-table">
        <thead><tr>
            <th>买入时间</th><th>买入价</th><th>卖出时间</th><th>卖出价</th>
            <th>股数</th><th>盈亏</th><th>收益率</th><th>原因</th>
        </tr></thead><tbody>`;

    trades.forEach(t => {
        const pnlClass = t.pnl >= 0 ? 'positive' : 'negative';
        const pnlSign = t.pnl >= 0 ? '+' : '';
        html += `<tr>
            <td>${formatTime(t.buy_time)}</td>
            <td>${t.buy_price}</td>
            <td>${formatTime(t.sell_time)}</td>
            <td>${t.sell_price}</td>
            <td>${t.shares}</td>
            <td class="${pnlClass}" style="color:var(--${t.pnl >= 0 ? 'red' : 'green'})">${pnlSign}${t.pnl}</td>
            <td class="${pnlClass}" style="color:var(--${t.pnl_pct >= 0 ? 'red' : 'green'})">${pnlSign}${t.pnl_pct}%</td>
            <td>${reasonMap[t.reason] || t.reason}</td>
        </tr>`;
    });

    html += '</tbody></table>';
    el.innerHTML = html;
}

function markTrades(trades) {
    if (!candleSeries || trades.length === 0) return;

    // 在K线图上叠加交易标记
    const markers = [];
    trades.forEach(t => {
        markers.push({
            time: t.buy_time,
            position: 'belowBar',
            color: '#FF5252',
            shape: 'arrowUp',
            text: `B ${t.buy_price}`,
        });
        markers.push({
            time: t.sell_time,
            position: 'aboveBar',
            color: '#69F0AE',
            shape: 'arrowDown',
            text: `S ${t.sell_price}`,
        });
    });
    markers.sort((a, b) => a.time - b.time);
    candleSeries.setMarkers(markers);
}

function closeBacktest() {
    document.getElementById('backtestPanel').classList.add('hidden');
    // 恢复原来的买卖点标记
    if (state.analysisData && candleSeries) {
        drawBSP(state.analysisData);
    }
}
