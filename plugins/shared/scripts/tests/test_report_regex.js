const assert = require('node:assert/strict');
const {Worker: ThreadWorker} = require('node:worker_threads');

module.exports = async function runRegexTests(harness) {
    const {context, document, reportTest, query, counts, visible, visibleJobUrls,
        renderGroupFixture, originalFilterData, downloads, issue, affected, status, release} = harness;
    const blobs = new Map();
    const workers = [];
    class IsolatedWorker {
        constructor(url) {
            this.thread = new ThreadWorker(`
                const {parentPort} = require('node:worker_threads');
                let compilations = 0;
                const NativeRegExp = RegExp;
                global.RegExp = class extends NativeRegExp {
                    constructor(...args) { super(...args); compilations++; }
                };
                global.self = {postMessage: data => parentPort.postMessage({...data, compilations})};
                parentPort.on('message', data => self.onmessage({data}));
            ` + blobs.get(url).content, {eval: true});
            this.thread.on('message', data => {
                this.result = data;
                const deliver = () => this.onmessage?.({data});
                if (this.hold) this.deliver = deliver;
                else deliver();
            });
            this.thread.on('error', error => this.onerror?.(error));
            workers.push(this);
        }
        postMessage(data) { this.payload = data; this.thread.postMessage(data); }
        terminate() { this.terminated = true; this.thread.terminate(); }
    }
    context.Worker = IsolatedWorker;
    context.setTimeout = (callback, delay) => delay === 1000 ? setTimeout(callback, delay) : (callback(), 0);
    context.clearTimeout = clearTimeout;
    context.URL.createObjectURL = blob => {
        const url = 'blob:regex-test-' + blobs.size;
        blobs.set(url, blob); downloads.push(blob); return url;
    };
    context.URL.revokeObjectURL = url => blobs.delete(url);
    const pause = () => new Promise(resolve => setTimeout(resolve, 5));
    async function until(predicate) {
        const deadline = Date.now() + 5000;
        while (!predicate()) {
            assert(Date.now() < deadline, 'regex test did not settle');
            await pause();
        }
    }
    const input = document.getElementById('report-filter');
    assert.equal(document.getElementById('filter-regex'), null);
    const error = document.getElementById('report-filter-error');
    const invalid = () => input.getAttribute('aria-invalid') === 'true';
    async function regex(pattern) { query(pattern); await until(() => !reportTest.pendingRegex); }
    try {
        query('');
        const punctuation = issue(5, 'literal [a+b].* token', [affected('literal.job[0]', 'punctuation')]);
        const pathological = issue(6, 'pathological', [affected('slow-job', 'slow')], {root_cause: 'a'.repeat(20000) + '!'});
        const originals = originalFilterData.releases_data['4.20'].issues;
        const issues = [...originals, punctuation, pathological];
        renderGroupFixture({'4.20': release(issues)}, {'4.20': [...originalFilterData.status_data['4.20'], status(punctuation.affected_jobs[0]), status(pathological.affected_jobs[0])]});
        reportTest.data.pr_data = originalFilterData.pr_data;
        reportTest.data.pr_status = null;
        const prTab = document.getElementById('tab-pull-requests');
        prTab.textContent = ''; reportTest.renderPRs(prTab);
        query('');
        const baseline = counts();
        await regex('[');
        assert(invalid()); assert.equal(counts(), baseline);
        await regex('^(ADD CAPABILITY|remove capability)$');
        assert(!invalid());
        assert.deepEqual(visible('#tab-periodics .issue-row').map(row => row.reportIssue.number), [1, 2]);
        assert.equal(workers.at(-1).result.compilations, 1);
        query(''); assert.equal(counts(), baseline); assert(!invalid());
        await regex('^LITERAL\\.JOB\\[0\\]$');
        assert.deepEqual(visibleJobUrls(), [punctuation.affected_jobs[0].url]);
        await regex('\\[a\\+b\\]\\.\\*');
        assert.deepEqual(visibleJobUrls(), [punctuation.affected_jobs[0].url]);
        await regex('^(ROOTNEEDLE|chaincause|chainevidence|chainquote)$');
        assert.deepEqual(visible('#tab-periodics .issue-row').map(row => row.reportIssue.number), [1]);
        for (const pattern of ['^chaincause$', '^chainevidence$', '^chainquote$']) {
            await regex(pattern);
            assert.deepEqual(visible('#tab-periodics .issue-row').map(row => row.reportIssue.number), [1]);
        }
        await regex('^repeated-job$');
        assert.deepEqual(visibleJobUrls(), originals.filter(entry => [1, 4].includes(entry.number)).flatMap(entry => entry.affected_jobs.filter(job => job.name === 'repeated-job').map(job => job.url)).concat([undefined]).sort());
        await regex('^other-[a-z]+$');
        assert.deepEqual(visibleJobUrls(), [originals[1].affected_jobs[0].url]);
        for (const pattern of ['SEVERITY_ONLY', 'BUG_ONLY', 'REMEDIATION_ONLY', 'TYPE_ONLY', 'SCENARIO_ONLY']) {
            await regex(pattern);
            assert.equal(visible('#tab-periodics .issue-row').length, 0);
            assert.equal(visibleJobUrls().length, 0);
        }
        await regex('^rootneedle$');
        const retained = counts();
        const retainedUrls = visibleJobUrls();
        await regex('[');
        assert(invalid()); assert(error.textContent.includes('Invalid regular expression'));
        const invalidWorkers = workers.length;
        assert.equal(counts(), retained); assert.deepEqual(visibleJobUrls(), retainedUrls);
        document.getElementById('export-json').click();
        const exported = JSON.parse(downloads.at(-1).content);
        assert.equal(exported.filter, '^rootneedle$'); assert.equal(exported.filter_mode, 'regex');
        assert.deepEqual(exported.issues.map(entry => entry.title), ['add capability']);
        document.getElementById('export-csv').click();
        assert(downloads.at(-1).content.includes('add capability'));
        const today = document.getElementById('filter-today');
        today.checked = true; today.dispatch('change');
        assert(invalid()); assert(visibleJobUrls().length < retainedUrls.length);
        document.getElementById('button-pull-requests').click();
        assert.equal(counts(), 'Failures: 0/1'); assert(invalid());
        document.getElementById('button-periodics').click();
        today.checked = false; today.dispatch('change');
        assert.equal(counts(), retained);
        assert.equal(workers.length, invalidWorkers);
        await regex('^remove capability$'); assert(!invalid());
        await regex('^ADD PR CAPABILITY$');
        document.getElementById('button-pull-requests').click();
        assert.equal(counts(), 'Failures: 1/1');
        document.getElementById('export-json').click();
        assert.deepEqual(JSON.parse(downloads.at(-1).content).issues.map(entry => entry.title), ['add PR capability']);
        document.getElementById('button-bugs').click(); assert.equal(counts(), '');
        document.getElementById('button-periodics').click();
        await regex('^legacy-job$'); assert.equal(visibleJobUrls().length, 1);
        today.checked = true; today.dispatch('change');
        assert.equal(visible('#tab-periodics .issue-row').length, 0);
        assert.equal(visibleJobUrls().length, 0);
        assert(counts().startsWith('Jobs: 0/')); assert(counts().includes('Failures: 0/'));
        today.checked = false; today.dispatch('change');
        query(''); assert.equal(counts(), baseline); assert(!invalid());
        await regex('add|remove');
        assert.equal(visible('#tab-periodics .issue-row').length, 2);
        query('^rootneedle$');
        const stale = workers.at(-1); stale.hold = true;
        await until(() => Boolean(stale.deliver));
        query('^remove capability$'); await until(() => !reportTest.pendingRegex);
        const current = counts(); stale.deliver(); assert.equal(counts(), current);
        assert.equal(reportTest.appliedFilter.query, '^remove capability$');
        query('^rootneedle$');
        const resetStale = workers.at(-1); resetStale.hold = true;
        await until(() => Boolean(resetStale.deliver));
        query(''); resetStale.deliver(); assert.equal(counts(), baseline); assert(!invalid());
        await regex('^remove capability$');
        const heartbeat = new Promise(resolve => setTimeout(() => resolve('UI responsive'), 20));
        query('(a+)+$'); const slow = workers.at(-1);
        assert.equal(await heartbeat, 'UI responsive');
        await until(() => !reportTest.pendingRegex);
        assert(invalid()); assert(error.textContent.includes('timed out'));
        assert(slow.terminated); assert.equal(counts(), current);
        assert.equal(reportTest.appliedFilter.query, '^remove capability$');
        await regex('^rootneedle$'); assert(!invalid());
        const beforeUnavailable = counts();
        context.Worker = undefined;
        await regex('unavailable-worker');
        assert(invalid()); assert(error.textContent.includes('Web Worker support'));
        assert.equal(counts(), beforeUnavailable);
        context.Worker = IsolatedWorker;
        await regex('a'.repeat(4097));
        assert(invalid()); assert(error.textContent.includes('maximum 4096'));
        assert.equal(counts(), beforeUnavailable);
        await regex('^rootneedle$'); assert(!invalid());
        assert(workers.every(worker => worker.terminated)); assert.equal(blobs.size, 0);
        assert(workers.every(worker => worker.payload.texts.every(text => !['SEVERITY_ONLY', 'BUG_ONLY', 'REMEDIATION_ONLY'].includes(text))));
        query('');
        console.log('PASS isolated regex regressions: regex-only initial matching, escaped punctuation, field anchors/alternation/classes, allowed fields, invalid/recovery/export, Today/tabs/counters, reset, real worker timeout/heartbeat, one compilation and stale-response rejection');
    } finally {
        workers.forEach(worker => worker.terminate());
    }
};
