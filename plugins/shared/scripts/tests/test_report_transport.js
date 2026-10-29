const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

module.exports = function({context, document, renderer, reportHTML}) {
    const assignment = reportHTML.match(/<script>(window.REPORT_DATA = [\s\S]*?;)<\/script>/)[1];
    vm.runInContext(assignment, context);
    vm.runInContext(renderer, context);
    assert.equal(document.getElementById('loading').style.display, 'none');
    assert.equal(document.querySelector('.container').style.display, '');
    const metrics = context.window.REPORT_DATA.releases_data['4.20'].issues[0].affected_jobs[0].metrics;
    assert.equal(metrics.io.aveq[0], '0.9XXXXXX999999999');
    const charts = [];
    context.Chart = function(canvas, config) { charts.push(config); };
    vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../../../microshift-ci/scripts/pcp-graphs/pcp-charts.js'), 'utf8'), context);
    const grid = document.createElement('div');
    for (const [kind, render] of [['cpu', 'renderCpu'], ['mem', 'renderMem'], ['io', 'renderIo'], ['disk', 'renderDisk']]) {
        context.pcpCharts[render](grid, metrics[kind]);
    }
    assert.equal(charts.length, 5);
    assert.deepEqual(Array.from(charts[3].data.datasets[1].data), [null, 2]);
    assert.deepEqual(Array.from(charts[0].data.datasets[0].data), [10, 20]);
    for (const chart of charts) {
        assert.deepEqual(Array.from(chart.data.labels), ['now', 'later']);
        for (const dataset of chart.data.datasets) {
            assert.equal(dataset.data.length, 2);
            assert(dataset.data.every(value => value === null || typeof value === 'number' && Number.isFinite(value)));
        }
    }
    assert(grid.children[1].textContent.includes('Peak Used: 2.00 GB'));
    assert(grid.children[1].textContent.includes('Total: 8.00 GB'));
    assert(!grid.textContent.includes('NaN'));
    metrics.mem.total_gb = ['XXXXXXXX', null];
    metrics.cpu.user = ['', '1XXXX2'];
    context.pcpCharts.renderMem(grid, metrics.mem);
    context.pcpCharts.renderCpu(grid, metrics.cpu);
    assert.equal(charts.at(-2).options.scales.y.max, undefined);
    assert.deepEqual(Array.from(charts.at(-1).data.datasets[0].data), [null, null]);
    metrics.cpu.user = ['1XXXX2', '20'];
    context.pcpCharts.renderCpu(grid, metrics.cpu);
    assert(grid.children.at(-1).textContent.includes('Avg Total: 23.0%'));
    const numericCpu = {timestamps: ['now', 'later'], user: [0, -1], sys: [1, 2], iowait: [0, 1]};
    context.pcpCharts.renderCpu(grid, numericCpu);
    assert.deepEqual(Array.from(charts.at(-1).data.datasets[0].data), [0, -1]);
    assert(grid.children.at(-1).textContent.includes('Avg Total: 1.5%'));
    assert.deepEqual(numericCpu.user, [0, -1]);
    for (const [sys, iowait, expected] of [
        [[1], [0, 1], '11.0%'],
        [[1, 2], [0], '11.0%'],
        [[], [], '0.0%'],
        [[null, 'XXXXXX'], ['XXXXXX', null], '0.0%'],
        [[0], [0], '0.0%']
    ]) {
        const user = expected === '0.0%' ? [0, 'XXXXXX'] : [10, 20];
        context.pcpCharts.renderCpu(grid, {timestamps: ['now', 'later'], user, sys, iowait});
        assert(grid.children.at(-1).textContent.includes('Avg Total: ' + expected));
        assert.deepEqual(Array.from(charts.at(-1).data.datasets[0].data), user.map(value => typeof value === 'number' ? value : null));
    }
    for (const [total_gb, expected, gaps] of [
        [['XXXXXXXX', '8'], '8.00 GB', [null, 8]],
        [['XXXXXXXX', '0'], '0.00 GB', [null, 0]],
        [[0, 8], '0.00 GB', [0, 8]],
        [['XXXXXXXX', null], '-', [null, null]],
        [[], '-', []]
    ]) {
        context.pcpCharts.renderMem(grid, Object.assign({}, metrics.mem, {total_gb}));
        assert(grid.children.at(-1).textContent.includes('Total: ' + expected));
        const dataset = charts.at(-1).data.datasets.find(series => series.label === 'Total');
        assert.deepEqual(dataset ? Array.from(dataset.data) : [], gaps);
    }
    const validData = context.window.REPORT_DATA;
    for (const damaged of [undefined, {releases_data: {'4.20': {issues: [null]}}}]) {
        context.window.REPORT_DATA = damaged;
        vm.runInContext(renderer, context);
        const loading = document.getElementById('loading');
        assert.equal(loading.style.display, 'flex');
        assert.equal(loading.getAttribute('role'), 'alert');
        assert(loading.textContent.includes('Unable to display this report'));
        assert.equal(document.querySelector('.container').style.display, 'none');
    }
    context.window.REPORT_DATA = undefined;
    assert.throws(() => vm.runInContext(assignment.replace('"0.9XXXXXX999999999"', '0.9XXXXXX999999999'), context), /Invalid or unexpected token/);
    vm.runInContext(renderer, context);
    assert(document.getElementById('loading').textContent.includes('Unable to display this report'));
    context.window.REPORT_DATA = validData;
    console.log('PASS censored report transport: full HTML assignment, renderer, all chart consumers, masked gaps and parse/render errors');
};
