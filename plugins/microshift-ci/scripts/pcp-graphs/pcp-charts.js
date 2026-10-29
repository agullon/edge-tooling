/**
 * Shared PCP chart rendering functions used by both the CI Doctor report
 * and the standalone PCP dashboard.
 *
 * Consumers call pcpCharts.init(opts) once, then pcpCharts.renderCpu(grid, d), etc.
 * opts.cardClass   — CSS class for card container (default: 'chart-card')
 * opts.headingTag  — heading element tag (default: 'h3')
 * opts.statsClass  — CSS class for stats row (default: 'stats-row')
 * opts.onChart     — callback(chartInstance) for lifecycle tracking (optional)
 */
var pcpCharts = (function() {
    var _opts = { cardClass: 'chart-card', headingTag: 'h3', statsClass: 'stats-row', onChart: null };

    function init(opts) {
        if (opts) {
            if (opts.cardClass) _opts.cardClass = opts.cardClass;
            if (opts.headingTag) _opts.headingTag = opts.headingTag;
            if (opts.statsClass) _opts.statsClass = opts.statsClass;
            if (opts.onChart) _opts.onChart = opts.onChart;
        }
    }

    function makeCard(grid, title) {
        var card = document.createElement('div');
        card.className = _opts.cardClass;
        var header = document.createElement('div');
        header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;';
        var h = document.createElement(_opts.headingTag);
        h.textContent = title;
        h.style.margin = '0';
        header.appendChild(h);
        var fsBtn = document.createElement('button');
        fsBtn.className = 'pcp-fs-btn';
        fsBtn.title = 'Toggle fullscreen';
        fsBtn.setAttribute('aria-label', 'Toggle fullscreen');
        fsBtn.textContent = '⛶';
        fsBtn.addEventListener('click', function() { toggleFullscreen(card); });
        header.appendChild(fsBtn);
        card.appendChild(header);
        var canvas = document.createElement('canvas');
        card.appendChild(canvas);
        grid.appendChild(card);
        return { card: card, canvas: canvas };
    }

    function toggleFullscreen(card) {
        if (document.fullscreenElement === card) {
            document.exitFullscreen();
        } else {
            card.requestFullscreen().catch(function() {});
        }
    }

    function addStats(card, items) {
        var row = document.createElement('div');
        row.className = _opts.statsClass;
        items.forEach(function(it) {
            var span = document.createElement('span');
            span.appendChild(document.createTextNode(it.label + ': '));
            var val = document.createElement('span');
            val.className = 'val';
            val.textContent = it.value;
            span.appendChild(val);
            row.appendChild(span);
        });
        card.appendChild(row);
    }

    function samples(arr) {
        return arr.map(function(value) {
            if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim())) return null;
            var number = Number(value);
            return Number.isFinite(number) ? number : null;
        });
    }

    function peak(arr) {
        var valid = arr.filter(function(value) { return value !== null; });
        return valid.length ? Math.max.apply(null, valid) : 0;
    }
    function avg(arr) {
        var valid = arr.filter(function(value) { return value !== null; });
        return valid.length ? valid.reduce(function(total, value) { return total + value; }, 0) / valid.length : 0;
    }

    function lineOpts(yLabel, yMax) {
        return {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }, tooltip: { mode: 'index', intersect: false } },
            scales: {
                x: { ticks: { maxTicksLimit: 8, maxRotation: 0, font: { size: 10 } }, grid: { display: false } },
                y: { beginAtZero: true, max: yMax, title: { display: true, text: yLabel, font: { size: 11 } }, ticks: { font: { size: 10 } } }
            }
        };
    }

    function track(chart) {
        if (_opts.onChart) _opts.onChart(chart);
    }

    function renderCpu(grid, d) {
        d = Object.assign({}, d, {user: samples(d.user), sys: samples(d.sys), iowait: samples(d.iowait)});
        var c = makeCard(grid, 'CPU Usage');
        var chart = new Chart(c.canvas, { type: 'line', data: { labels: d.timestamps, datasets: [
            { label: 'User', data: d.user, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.15)', fill: true, pointRadius: 0, borderWidth: 1.5, tension: 0.2, order: 3 },
            { label: 'I/O Wait', data: d.iowait, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.15)', fill: true, pointRadius: 0, borderWidth: 1.5, tension: 0.2, order: 2 },
            { label: 'System', data: d.sys, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.15)', fill: true, pointRadius: 0, borderWidth: 1.5, tension: 0.2, order: 1 }
        ] }, options: lineOpts('CPU %', 100) });
        track(chart);
        addStats(c.card, [
            { label: 'Peak User', value: peak(d.user).toFixed(1) + '%' },
            { label: 'Peak System', value: peak(d.sys).toFixed(1) + '%' },
            { label: 'Peak I/O Wait', value: peak(d.iowait).toFixed(1) + '%' },
            { label: 'Avg Total', value: avg(d.user.map(function(value, index) {
                return value === null || d.sys[index] === null || d.iowait[index] === null ? null : value + d.sys[index] + d.iowait[index];
            })).toFixed(1) + '%' }
        ]);
    }

    function memOpts(yMax) {
        var opts = lineOpts('GB', yMax);
        opts.scales.y.stacked = true;
        return opts;
    }

    function renderMem(grid, d) {
        d = Object.assign({}, d, {used_gb: samples(d.used_gb), cached_gb: samples(d.cached_gb), total_gb: samples(d.total_gb || [])});
        var c = makeCard(grid, 'Memory Usage');
        var ds = [
            { label: 'Used', data: d.used_gb, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.4)', fill: 'origin', pointRadius: 0, borderWidth: 1.5, tension: 0.2, stack: 'mem', order: 2 },
            { label: 'Cached', data: d.cached_gb, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.4)', fill: '-1', pointRadius: 0, borderWidth: 1.5, tension: 0.2, stack: 'mem', order: 1 }
        ];
        if (d.total_gb && d.total_gb.length) {
            ds.push({ label: 'Total', data: d.total_gb, borderColor: '#333', backgroundColor: 'transparent', fill: false, pointRadius: 0, borderWidth: 1.5, borderDash: [5, 3], tension: 0, order: 0 });
        }
        var maxY = peak(d.total_gb) > 0 ? Math.ceil(peak(d.total_gb) * 1.1) : undefined;
        var chart = new Chart(c.canvas, { type: 'line', data: { labels: d.timestamps, datasets: ds }, options: memOpts(maxY) });
        track(chart);
        addStats(c.card, [
            { label: 'Peak Used', value: peak(d.used_gb).toFixed(2) + ' GB' },
            { label: 'Peak Cached', value: peak(d.cached_gb).toFixed(2) + ' GB' },
            { label: 'Total', value: d.total_gb.length && d.total_gb[0] !== null ? d.total_gb[0].toFixed(2) + ' GB' : '-' }
        ]);
    }

    function renderIo(grid, d) {
        d = Object.assign({}, d, {bi: samples(d.bi), bo: samples(d.bo), await: samples(d.await), aveq: samples(d.aveq)});
        var c1 = makeCard(grid, 'Disk I/O Throughput');
        var chart1 = new Chart(c1.canvas, { type: 'line', data: { labels: d.timestamps, datasets: [
            { label: 'Read', data: d.bi, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.15)', fill: true, pointRadius: 0, borderWidth: 1.5, tension: 0.2 },
            { label: 'Write', data: d.bo, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.15)', fill: true, pointRadius: 0, borderWidth: 1.5, tension: 0.2 }
        ] }, options: lineOpts('OPS') });
        track(chart1);
        addStats(c1.card, [
            { label: 'Peak Read', value: peak(d.bi).toFixed(0) + ' OPS' },
            { label: 'Peak Write', value: peak(d.bo).toFixed(0) + ' OPS' }
        ]);

        var c2 = makeCard(grid, 'Disk I/O Latency');
        var chart2 = new Chart(c2.canvas, { type: 'line', data: { labels: d.timestamps, datasets: [
            { label: 'Await (ms)', data: d.await, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.15)', fill: true, pointRadius: 0, borderWidth: 1.5, tension: 0.2, yAxisID: 'y' },
            { label: 'Queue Length', data: d.aveq, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.15)', fill: true, pointRadius: 0, borderWidth: 1.5, tension: 0.2, yAxisID: 'y1' }
        ] }, options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }, tooltip: { mode: 'index', intersect: false } },
            scales: {
                x: { ticks: { maxTicksLimit: 8, maxRotation: 0, font: { size: 10 } }, grid: { display: false } },
                y: { position: 'left', title: { display: true, text: 'Await (ms)', font: { size: 11 } }, beginAtZero: true, ticks: { font: { size: 10 } } },
                y1: { position: 'right', title: { display: true, text: 'Queue Length', font: { size: 11 } }, beginAtZero: true, grid: { drawOnChartArea: false }, ticks: { font: { size: 10 } } }
            }
        } });
        track(chart2);
        addStats(c2.card, [
            { label: 'Peak Await', value: peak(d.await).toFixed(1) + ' ms' },
            { label: 'Peak Queue', value: peak(d.aveq).toFixed(2) }
        ]);
    }

    function renderDisk(grid, d) {
        d = Object.assign({}, d, {partitions: d.partitions.map(function(partition) {
            return Object.assign({}, partition, {used_pct: samples(partition.used_pct)});
        })});
        var c = makeCard(grid, 'Disk Usage');
        var colors = ['#8b5cf6', '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#84cc16'];
        var datasets = d.partitions.map(function(p, i) {
            var lbl = p.device;
            if (p.mountdir) lbl += ' (' + p.mountdir + ')';
            if (p.capacity_gb) lbl += ' ' + p.capacity_gb + 'G';
            return { label: lbl, data: p.used_pct, borderColor: colors[i % colors.length], backgroundColor: 'transparent', fill: false, pointRadius: 0, borderWidth: 1.5, tension: 0.2 };
        });
        var chart = new Chart(c.canvas, { type: 'line', data: { labels: d.timestamps, datasets: datasets }, options: lineOpts('Usage %', 100) });
        track(chart);
        var statsItems = d.partitions.map(function(p) {
            var pctArr = p.used_pct.filter(function(v) { return v !== null; });
            return { label: 'Peak ' + (p.mountdir || p.device), value: peak(pctArr).toFixed(1) + '%' };
        });
        addStats(c.card, statsItems.slice(0, 4));
    }

    return {
        init: init,
        renderCpu: renderCpu,
        renderMem: renderMem,
        renderIo: renderIo,
        renderDisk: renderDisk
    };
})();
