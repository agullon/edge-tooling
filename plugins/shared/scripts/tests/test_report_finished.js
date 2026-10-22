const assert = require('node:assert/strict');
const fs = require('node:fs');

module.exports = function(data, today, release) {
    const sourceISO = '2026-10-15T01:21:52Z';
    const epoch = Date.parse(sourceISO) / 1000;
    const yesterday = new Date(Date.parse(today) - 86400000).toISOString().slice(0, 10);
    const fixtures = [
        [sourceISO, sourceISO], [epoch, sourceISO], [String(epoch), sourceISO],
        [0, '1970-01-01T00:00:00Z'], ['0', '1970-01-01T00:00:00Z'],
        [-1, '1969-12-31T23:59:59Z'],
        ['', ''], [null, ''], [undefined, ''], ['not-a-date', ''],
        ['2026junk', ''], ['2026-13-15T01:21:52Z', ''], ['2026-02-30T01:21:52Z', ''],
        ['2026-10-15T01:21:52', ''], [Infinity, ''], [1e30, ''], [true, ''], [{}, ''],
        [today + 'T00:00:01Z', today + 'T00:00:01Z'],
        [Date.parse(today + 'T00:00:02Z') / 1000, today + 'T00:00:02Z'],
        [today + 'T00:30:00+02:00', yesterday + 'T22:30:00Z'],
        [yesterday + 'T23:30:00-02:00', today + 'T01:30:00Z'],
    ].map(([finished, iso], index) => ({job: 'timestamp-' + index, url: 'https://example.invalid/time-' + index,
        status: 'success', duration: 60, finished, iso}));
    data.releases_data = {'timestamps': release([])};
    data.status_data = {'timestamps': fixtures};
    data.pr_data = null; data.pr_status = null;
    let suppliedJobs = [];
    if (process.argv[3]) {
        const supplied = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
        suppliedJobs = Object.values(supplied.status_data || {}).flatMap(jobs => jobs || []);
        data.releases_data.supplied = release([]);
        data.status_data.supplied = suppliedJobs;
    }
    return async function({document, reportTest}) {
        const table = document.getElementById('release-timestamps').querySelector('.jobs-table');
        const rows = () => table.querySelectorAll('.job-row');
        const order = () => rows().map(row => row.reportJob.iso || '');
        const expectedOrder = fixtures.map(job => job.iso || '').sort();
        assert.deepEqual(order(), expectedOrder);
        rows().forEach(row => assert.equal(row.cells[2].textContent,
            row.reportJob.iso ? row.reportJob.iso.replace('T', ' ').slice(0, 16) : '', row.reportJob.job));
        const sourceRow = rows().find(row => row.reportJob.finished === sourceISO);
        assert.equal(sourceRow.cells[2].textContent, '2026-10-15 01:21');
        const header = table.querySelectorAll('th')[2];
        header.click(); assert.deepEqual(order(), expectedOrder.slice().reverse());
        header.click(); assert.deepEqual(order(), expectedOrder);
        if (suppliedJobs.length) {
            const suppliedRows = document.getElementById('release-supplied').querySelectorAll('.job-row');
            assert.equal(suppliedRows.length, suppliedJobs.length);
            suppliedRows.forEach(row => {
                const value = row.reportJob.finished;
                const expected = value ? new Date(value).toISOString().replace('T', ' ').slice(0, 16) : '';
                assert.equal(row.cells[2].textContent, expected);
            });
            console.log('PASS supplied Finished timestamps: ' + suppliedRows.length + ' actual job rows');
        }
        const todayToggle = document.getElementById('filter-today');
        todayToggle.checked = true; todayToggle.dispatch('change');
        const expectedToday = fixtures.filter(job => job.iso.startsWith(today));
        const visible = () => rows().filter(row => row.style.display !== 'none');
        assert.deepEqual(visible().map(row => row.reportJob.job).sort(), expectedToday.map(job => job.job).sort());
        const toc = document.querySelector('.toc-status[data-release="timestamps"]');
        assert(toc.textContent.includes(`${expectedToday.length}/${expectedToday.length} passed (100%)`));
        const input = document.getElementById('report-filter');
        input.value = '^timestamp-18$'; input.dispatch('input');
        const deadline = Date.now() + 5000;
        while (reportTest.pendingRegex) {
            assert(Date.now() < deadline, 'timestamp regex did not settle');
            await new Promise(resolve => setTimeout(resolve, 5));
        }
        assert.equal(visible().length, 1);
        assert.equal(document.getElementById('filter-count').textContent, 'Jobs: 1/' + expectedToday.length + ', Failures: 0/0');
        input.value = ''; input.dispatch('input');
        assert.equal(visible().length, expectedToday.length);
        todayToggle.checked = false; todayToggle.dispatch('change');
        assert.equal(visible().length, fixtures.length);
        console.log('PASS Finished regressions: ISO/epoch seconds/zero/invalid, UTC boundaries, full-precision initial/click sorting, Today/regex/reset and TOC counts');
    };
};
