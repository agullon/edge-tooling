const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function descendants(element) {
    return element.children.flatMap(child => [child, ...descendants(child)]);
}
function matches(element, token) {
    const attributes = [...token.matchAll(/\[([^=\]]+)(?:="([^"]*)")?\]/g)];
    if (!attributes.every(([, name, value]) => element.hasAttribute(name) &&
        (value === undefined || element.getAttribute(name) === value))) return false;
    token = token.replace(/\[[^\]]*\]/g, '');
    const tag = token.match(/^[a-z][\w-]*/i);
    const id = token.match(/#([\w-]+)/);
    const classes = [...token.matchAll(/\.([\w-]+)/g)];
    return (!tag || element.tag === tag[0]) && (!id || element.id === id[1]) &&
        classes.every(([, name]) => element.classList.contains(name));
}
function select(root, selector) {
    return descendants(root).filter(element => selector.split(',').some(group => {
        const tokens = group.trim().split(/\s+/);
        if (!matches(element, tokens.pop())) return false;
        let ancestor = element.parent;
        while (tokens.length) {
            const token = tokens.pop();
            while (ancestor && !matches(ancestor, token)) ancestor = ancestor.parent;
            if (!ancestor) return false;
            ancestor = ancestor.parent;
        }
        return true;
    }));
}
class Element {
    constructor(tag) {
        this.tag = tag;
        this.children = [];
        this.attributes = {};
        this.style = {};
        this.listeners = {};
        this.dataset = {};
        this.nodeType = 1;
        this.text = '';
        this.className = '';
        this.value = '';
        this.checked = false;
        this.classList = {
            contains: name => this.className.split(' ').includes(name),
            add: (...names) => { this.className = [...new Set([...this.className.split(' ').filter(Boolean), ...names])].join(' '); },
            remove: (...names) => { this.className = this.className.split(' ').filter(name => !names.includes(name)).join(' '); },
            toggle: (name, force) => {
                const enabled = force === undefined ? !this.classList.contains(name) : force;
                this.classList[enabled ? 'add' : 'remove'](name);
            }
        };
    }
    appendChild(child) {
        if (child.parent) child.parent.removeChild(child);
        child.parent = this;
        this.children.push(child);
        return child;
    }
    removeChild(child) {
        const index = this.children.indexOf(child);
        if (index === -1) throw new Error('Cannot remove a non-child element');
        this.children.splice(index, 1);
        child.parent = null;
        return child;
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return this.attributes[name] ?? this[name] ?? null; }
    hasAttribute(name) { return this.getAttribute(name) !== null; }
    addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
    dispatch(name) { (this.listeners[name] || []).forEach(handler => handler.call(this, {target: this, currentTarget: this})); }
    click() { this.dispatch('click'); }
    querySelectorAll(selector) { return select(this, selector); }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    closest(selector) { return matches(this, selector) ? this : this.parent?.closest(selector) || null; }
    scrollIntoView() {}
    get cells() { return this.children; }
    get nextElementSibling() { return this.parent?.children[this.parent.children.indexOf(this) + 1] || null; }
    set textContent(text) {
        this.text = String(text);
        this.children.forEach(child => { child.parent = null; });
        this.children = [];
    }
    get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
}

function testElementParentage() {
    const parent = new Element('div');
    const oldChild = new Element('span');
    const oldSibling = new Element('span');
    const descendant = new Element('b');
    oldChild.appendChild(descendant);
    parent.appendChild(oldChild);
    parent.appendChild(oldSibling);
    parent.textContent = 'replacement';
    const newChild = new Element('i');
    parent.appendChild(newChild);
    const destination = new Element('div');
    destination.appendChild(oldChild);
    assert.deepEqual(parent.children, [newChild]);
    assert.equal(parent.textContent, 'replacement');
    assert.equal(newChild.parent, parent);
    assert.equal(oldChild.parent, destination);
    assert.equal(oldSibling.parent, null);
    assert.deepEqual(destination.children, [oldChild]);
    assert.equal(descendant.parent, oldChild);
    assert.deepEqual(oldChild.children, [descendant]);
    assert.equal(parent.appendChild(oldSibling), oldSibling);
    assert.deepEqual(parent.children, [newChild, oldSibling]);
    assert.equal(oldSibling.parent, parent);
    assert.equal(destination.appendChild(newChild), newChild);
    assert.deepEqual(parent.children, [oldSibling]);
    assert.deepEqual(destination.children, [oldChild, newChild]);
    assert.equal(newChild.parent, destination);
    assert.equal(destination.appendChild(oldChild), oldChild);
    assert.deepEqual(destination.children, [newChild, oldChild]);
    assert.equal(oldChild.parent, destination);
    assert.throws(() => parent.removeChild(newChild), /non-child/);
    assert.deepEqual(parent.children, [oldSibling]);
    assert.deepEqual(destination.children, [newChild, oldChild]);
    assert.equal(newChild.parent, destination);
    assert.throws(() => destination.removeChild(oldSibling), /non-child/);
    assert.deepEqual(destination.children, [newChild, oldChild]);
    assert.equal(oldSibling.parent, parent);
    assert.equal(parent.removeChild(oldSibling), oldSibling);
    assert.equal(oldSibling.parent, null);
    assert.deepEqual(parent.children, []);
    assert.throws(() => parent.removeChild(oldSibling), /non-child/);
    assert.deepEqual(parent.children, []);
    console.log('PASS Element parentage: text clearing detaches children, reuse preserves siblings, reparenting and non-child removal');
}
testElementParentage();

const today = new Date().toISOString().substring(0, 10);
const oldDay = '2020-01-01';
function affected(name, suffix, date = today) { return {name, url: 'https://example.invalid/' + suffix, date}; }
function issue(number, title, jobs, extra = {}) {
    return {number, title, affected_jobs: jobs, job_count: jobs.length, severity: 'HIGH', failure_type: 'test', ...extra};
}
function release(issues) {
    return {issues, total_failed: issues.reduce((total, entry) => total + entry.job_count, 0), breakdown: {build: 0, test: issues.length, infrastructure: 0}};
}
const addIssue = issue(1, 'add capability', [affected('repeated-job', 'current'), affected('legacy-job', 'old', oldDay)], {
    root_cause: 'rootneedle', causal_chain: [null, {cause: 'chaincause', evidence: 'chainevidence', quote: 'chainquote'}],
    severity: 'SEVERITY_ONLY', failure_type: 'TYPE_ONLY', next_steps: 'REMEDIATION_ONLY', scenarios: ['SCENARIO_ONLY'],
    bug_match: {duplicates: [{key: 'BUG_ONLY', summary: 'bug-only description', status: 'New'}]},
});
const issues = [addIssue, issue(2, 'remove capability', [affected('other-job', 'other')]), issue(3, 'historical', [affected('past-job', 'past', oldDay)]),
    issue(4, 'separate run', [affected('repeated-job', 'rival')], {root_cause: 'rivalneedle'})];
const crossIssue = issue(1, 'cross release', [affected('repeated-job', 'cross')], {root_cause: 'crossneedle', severity: 'CRITICAL'});
function status(job) {
    const iso = job.date.substring(0, 10) + 'T12:00:00Z';
    const finished = job.name === 'repeated-job' ? iso : String(Date.parse(iso) / 1000);
    return {job: job.name, url: job.url, finished, duration: '60', status: 'failure'};
}
const periodicJobs = issues.flatMap(entry => entry.affected_jobs).map(status);
periodicJobs.push(status(affected('passing-job', 'passing')));
periodicJobs.push(status({...affected('repeated-job', 'missing'), url: undefined}));
const data = {
    component_title: 'Probe', timestamp: today, date: today, commit_version: 'probe', commit_subject: '<subject>', commit_date: today,
    releases_data: {'4.20': release(issues), '4.21': release([crossIssue])},
    status_data: {'4.20': periodicJobs, '4.21': crossIssue.affected_jobs.map(status)},
    pr_data: {has_content: true, prs: [{number: 7, title: 'PR', failed: 1, issues: [issue(1, 'add PR capability', [affected('pr-only-job', 'pr', oldDay)])]}]},
    bugs_tab_data: {linked: [{key: 'BUG_ONLY', summary: 'add hidden bug', status: 'New'}], unlinked: [], jira_query_available: false},
};
const body = new Element('body');
const document = {
    body, createElement: tag => new Element(tag),
    createTextNode: text => Object.assign(new Element('#text'), {textContent: text}),
    getElementById: id => descendants(body).find(element => element.id === id) || null,
    querySelectorAll: selector => select(body, selector),
    querySelector: selector => select(body, selector)[0] || null,
    addEventListener() {},
};
function skeleton(tag, id, cls, parent = body) {
    const element = new Element(tag);
    element.id = id;
    element.className = cls || '';
    parent.appendChild(element);
    return element;
}
const container = skeleton('div', 'container', 'container');
['report-title', 'report-timestamp', 'diagnostics-slot', 'overview-slot', 'loading', 'filter-count', 'report-filter', 'export-json', 'export-csv'].forEach(id => skeleton('div', id, '', container));
['periodics', 'pull-requests', 'bugs', 'images'].forEach((tab, index) => {
    const button = skeleton('button', 'button-' + tab, 'tab-btn' + (index ? '' : ' active'), container);
    button.setAttribute('data-tab', tab);
    skeleton('div', 'tab-' + tab, 'tab-content' + (index ? '' : ' active'), container);
});
const downloads = [];
const handlers = {};
const location = {hash: '', href: 'https://example.invalid/report'};
const context = vm.createContext({
    document, window: {REPORT_DATA: data, addEventListener: (event, callback) => {handlers[event] = callback;}},
    location, navigator: {}, setTimeout: callback => {callback(); return 1;}, clearTimeout() {}, requestAnimationFrame: callback => callback(),
    Blob: class {constructor(parts) {this.content = parts.join('');}}, URL: {createObjectURL(blob) {downloads.push(blob); return 'blob:test';}, revokeObjectURL() {}},
    alert() {alerts++;}
});
let alerts = 0;
const renderer = fs.readFileSync(process.argv[2], 'utf8');
const rendererEnd = renderer.lastIndexOf('})();');
const testExports = 'window.reportTest = {data: D, renderOverview, renderPeriodics, applyReportFilter};\n';
vm.runInContext(renderer.slice(0, rendererEnd) + testExports + renderer.slice(rendererEnd), context);
const reportTest = context.window.reportTest;
const input = document.getElementById('report-filter');
const counts = () => document.getElementById('filter-count').textContent;
const visible = selector => document.querySelectorAll(selector).filter(row => row.style.display !== 'none');
const query = text => {input.value = text; input.dispatch('input');};
const visibleJobUrls = () => visible('#tab-periodics .job-row').map(row => row.reportJob.url).sort();
const crossBadge = document.querySelector('.release-badge[data-release="4.21"]');
assert(crossBadge.classList.contains('badge-critical'));
const jobTotal = periodicJobs.length + 1;
const failureTotal = issues.length + 1;
assert.equal(counts(), `Jobs: ${jobTotal}/${jobTotal}, Failures: ${failureTotal}/${failureTotal}`);
query('add');
assert.equal(counts(), `Jobs: ${addIssue.affected_jobs.length}/${jobTotal}, Failures: 1/${failureTotal}`);
assert.equal(visible('#tab-periodics .issue-row').length, 1);
for (const forbidden of ['SEVERITY_ONLY', 'BUG_ONLY', 'bug-only description', 'REMEDIATION_ONLY', 'SCENARIO_ONLY', 'TYPE_ONLY']) {
    query(forbidden);
    assert.equal(counts(), `Jobs: 0/${jobTotal}, Failures: 0/${failureTotal}`, forbidden);
    document.getElementById('export-json').click();
    assert.equal(JSON.parse(downloads.at(-1).content).issues.length, 0, forbidden);
    const beforeCsv = downloads.length;
    document.getElementById('export-csv').click();
    assert.equal(downloads.length, beforeCsv, forbidden);
}
for (const term of ['rootneedle', 'chaincause', 'chainevidence', 'chainquote', '  ROOTNEEDLE  ']) {
    query(term);
    assert.equal(counts(), `Jobs: 2/${jobTotal}, Failures: 1/${failureTotal}`, term);
    assert.deepEqual(visibleJobUrls(), addIssue.affected_jobs.map(job => job.url).sort(), term);
}
query('rivalneedle');
assert.deepEqual(visibleJobUrls(), [issues[3].affected_jobs[0].url]);
query('crossneedle');
assert.deepEqual(visibleJobUrls(), [crossIssue.affected_jobs[0].url]);
assert(crossBadge.classList.contains('badge-critical'));
query('rootneedle');
assert(crossBadge.classList.contains('badge-ok'));
query('other-job');
assert.equal(counts(), `Jobs: 1/${jobTotal}, Failures: 1/${failureTotal}`);
query('legacy-job');
assert.equal(counts(), `Jobs: 1/${jobTotal}, Failures: 1/${failureTotal}`);
query('repeated-job');
assert.equal(counts(), `Jobs: ${periodicJobs.filter(job => job.job === 'repeated-job').length + 1}/${jobTotal}, Failures: 3/${failureTotal}`);
query('passing-job');
assert.equal(counts(), `Jobs: 1/${jobTotal}, Failures: 0/${failureTotal}`);
query('does-not-match');
assert.equal(visible('#tab-periodics .detail-row').length, 0);
query('');
assert.equal(visible('#tab-periodics .detail-row').length, failureTotal);
assert.equal(counts(), `Jobs: ${jobTotal}/${jobTotal}, Failures: ${failureTotal}/${failureTotal}`);
const todayToggle = document.getElementById('filter-today');
todayToggle.checked = true;
todayToggle.dispatch('change');
const dayJobs = periodicJobs.filter(job => new Date(/^\d+$/.test(job.finished) ? Number(job.finished) * 1000 : job.finished).toISOString().startsWith(today)).length + 1;
const dayFailures = issues.filter(entry => entry.affected_jobs.some(job => job.date === today)).length + 1;
query('add');
assert.equal(counts(), `Jobs: 1/${dayJobs}, Failures: 1/${dayFailures}`);
query('legacy-job');
assert.equal(counts(), `Jobs: 0/${dayJobs}, Failures: 0/${dayFailures}`);
query('rootneedle');
assert.equal(counts(), `Jobs: 1/${dayJobs}, Failures: 1/${dayFailures}`);
query('add');
document.getElementById('button-pull-requests').click();
assert.equal(counts(), 'Failures: 1/1');
document.getElementById('button-bugs').click();
assert.equal(counts(), '');
assert.equal(visible('#tab-bugs tbody tr').length, 1);
document.getElementById('button-images').click();
assert.equal(counts(), '');
document.getElementById('button-periodics').click();
assert.equal(counts(), `Jobs: 1/${dayJobs}, Failures: 1/${dayFailures}`);
todayToggle.checked = false;
todayToggle.dispatch('change');
assert.equal(counts(), `Jobs: 2/${jobTotal}, Failures: 1/${failureTotal}`);
query('rootneedle');
todayToggle.checked = true;
todayToggle.dispatch('change');
assert.equal(counts(), `Jobs: 1/${dayJobs}, Failures: 1/${dayFailures}`);
query('add');
document.getElementById('export-json').click();
assert.equal(JSON.parse(downloads.at(-1).content).issues.length, 2);
document.getElementById('export-csv').click();
assert(downloads.at(-1).content.includes('add capability'));
document.getElementById('button-images').click();
query('legacy-job');
document.getElementById('export-json').click();
assert.deepEqual(JSON.parse(downloads.at(-1).content).issues.map(entry => entry.title), [addIssue.title]);
document.getElementById('export-csv').click();
assert(downloads.at(-1).content.includes(addIssue.title));
query('add');
location.hash = '#pr-7-1';
handlers.hashchange();
assert.equal(counts(), 'Failures: 1/1');
assert.equal(alerts, 6);
function renderGroupFixture(releases, statuses = {}) {
    query('');
    document.getElementById('button-periodics').click();
    reportTest.data.releases_data = releases;
    reportTest.data.status_data = statuses;
    const periodics = document.getElementById('tab-periodics');
    periodics.textContent = '';
    const overview = document.getElementById('overview-slot');
    overview.textContent = '';
    reportTest.renderOverview(overview);
    reportTest.renderPeriodics(periodics);
}
function assertGroupSummary(version, groupCount, runCount, breakdown, suffix = '') {
    const section = document.getElementById('release-' + version);
    const expected = `${groupCount} failure group${groupCount === 1 ? '' : 's'} affecting ${runCount}${suffix ? ' identified' : ''} failed job run${runCount === 1 ? '' : 's'}${suffix}`;
    assert.equal(section.querySelector('.release-badge').textContent, expected);
    const heading = section.querySelector('.failure-analysis-summary');
    assert.equal(Boolean(heading), Boolean(reportTest.data.releases_data[version].issues.length));
    if (heading) assert.equal(heading.textContent, 'Failure Analysis — ' + expected);
    const toc = document.querySelector(`.toc-counts[data-release="${version}"]`);
    assert.equal(toc.textContent, `${expected} (${breakdown[0]} build groups, ${breakdown[1]} test groups, ${breakdown[2]} infrastructure groups)`);
    assert.equal(section.querySelector('.bd-build').textContent, String(breakdown[0]));
    assert.equal(section.querySelector('.bd-test').textContent, String(breakdown[1]));
    assert.equal(section.querySelector('.bd-infra').textContent, String(breakdown[2]));
    assert(section.querySelector('.breakdown').textContent.includes('failure groups'));
    assert.equal(document.querySelector(`.overview-count[data-release="${version}"]`).textContent, String(groupCount));
    assert.equal(document.querySelector(`.overview-summary[data-release="${version}"]`).textContent, expected);
}
const sameName = (run, date = today) => affected('same-job-name', run, date);
const sharedRun = sameName('shared');
const groupedIssues = [
    issue(1, 'historical build', [sameName('old-run', oldDay)], {failure_type: 'build'}),
    issue(2, 'shared primary', [sharedRun]),
    issue(3, 'shared secondary', [{...sharedRun, name: 'same-job-name-alias'}]),
    issue(4, 'independent run', [sameName('independent')]),
    issue(5, 'shared tertiary', [sharedRun]),
    issue(6, 'two run infrastructure', [sameName('new-run'), sameName('another-old-run', oldDay)], {failure_type: 'infrastructure'}),
];
const groupRelease = release(groupedIssues);
const otherRelease = release([issue(1, 'different release', [sameName('different-release')])]);
assert.equal(groupedIssues.reduce((total, entry) => total + entry.job_count, 0), 7);
const groupStatuses = [...new Map(groupedIssues.flatMap(entry => entry.affected_jobs).map(job => [job.url, status(job)])).values()];
renderGroupFixture({'5.0': groupRelease, 'other': otherRelease, 'empty': release([])}, {'5.0': groupStatuses, 'other': otherRelease.issues[0].affected_jobs.map(status), 'empty': []});
assertGroupSummary('5.0', 6, 5, [1, 4, 1]);
assertGroupSummary('other', 1, 1, [0, 1, 0]);
assertGroupSummary('empty', 0, 0, [0, 0, 0]);
assert(document.querySelector('#tab-periodics .toc').textContent.includes('0/0 passed (0%)'));
reportTest.applyReportFilter();
assertGroupSummary('5.0', 6, 5, [1, 4, 1]);
query('shared');
assertGroupSummary('5.0', 3, 1, [0, 3, 0]);
assert.equal(counts(), `Jobs: 1/${groupStatuses.length + 1}, Failures: 3/${groupedIssues.length + 1}`);
query('two run');
assertGroupSummary('5.0', 1, 2, [0, 0, 1]);
const groupToday = document.getElementById('filter-today');
groupToday.checked = true;
groupToday.dispatch('change');
assertGroupSummary('5.0', 1, 1, [0, 0, 1]);
query('');
assertGroupSummary('5.0', 5, 3, [0, 4, 1]);
document.getElementById('button-bugs').click();
assert.equal(counts(), '');
assertGroupSummary('5.0', 5, 3, [0, 4, 1]);
document.getElementById('button-periodics').click();
query('same-job-name');
assertGroupSummary('5.0', 5, 3, [0, 4, 1]);
assertGroupSummary('other', 1, 1, [0, 1, 0]);
query('no-group-matches');
assertGroupSummary('5.0', 0, 0, [0, 0, 0]);
groupToday.checked = false;
groupToday.dispatch('change');
query('');
assertGroupSummary('5.0', 6, 5, [1, 4, 1]);
const unidentified = release([issue(1, 'unknown one', [{name: 'same-name'}]), issue(2, 'unknown two', [{name: 'same-name'}])]);
renderGroupFixture({'unknown': unidentified});
assertGroupSummary('unknown', 2, 0, [0, 2, 0], ' (+2 associations without run URLs)');
query('unknown one');
assertGroupSummary('unknown', 1, 0, [0, 1, 0], ' (+1 associations without run URLs)');
const mixed = release([issue(1, 'mixed known', [sameName('known'), {name: 'missing old URL', date: oldDay}]), issue(2, 'mixed unknown', [{name: 'missing URL', date: today}])]);
renderGroupFixture({'mixed': mixed});
assertGroupSummary('mixed', 2, 1, [0, 2, 0], ' (+2 associations without run URLs)');
const mixedToday = document.getElementById('filter-today');
mixedToday.checked = true;
mixedToday.dispatch('change');
assertGroupSummary('mixed', 2, 1, [0, 2, 0], ' (+1 associations without run URLs)');
query('mixed known');
assertGroupSummary('mixed', 1, 1, [0, 1, 0]);
renderGroupFixture({'no-jobs': release([issue(1, 'no references', [])])});
assertGroupSummary('no-jobs', 1, 0, [0, 1, 0]);
if (process.argv[3]) {
    const supplied = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
    renderGroupFixture(supplied.releases_data, supplied.status_data);
    Object.entries(supplied.releases_data).forEach(([version, releaseData]) => {
        if (!releaseData || releaseData.collection_error) return;
        const groups = releaseData.issues || [];
        const jobs = groups.flatMap(entry => entry.affected_jobs || []);
        const runs = new Set(jobs.filter(job => job.url).map(job => job.url));
        const types = ['build', 'test', 'infrastructure'].map(type => groups.filter(entry =>
            (['build', 'infrastructure'].includes(entry.failure_type) ? entry.failure_type : 'test') === type).length);
        const unidentified = jobs.filter(job => !job.url).length;
        const suffix = unidentified ? ` (+${unidentified} associations without run URLs)` : '';
        assertGroupSummary(version, groups.length, runs.size, types, suffix);
        reportTest.applyReportFilter();
        assertGroupSummary(version, groups.length, runs.size, types, suffix);
        console.log(`SUPPLIED release ${version}: ${groups.length} failure groups affecting ${runs.size} failed job runs; ${jobs.length} associations; producer total_failed=${releaseData.total_failed}`);
    });
}
console.log('PASS failure group summaries: initial and dynamic 6 groups/5 distinct runs/7 associations, shared runs, multi-run groups, release scope, zero/empty, missing URLs and Today/search/tab reset');
console.log('PASS renderer filter regressions: allowed fields, excluded fields, group/job relationships, empty reset, tabs, Today-only intersection, counters, exports and deep links');
