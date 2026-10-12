#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT
mkdir -p "$test_dir/scripts" "$test_dir/jobs" "$test_dir/bin" "$test_dir/runs/demo/tnf"
cp "$source_dir/scripts/status.sh" "$test_dir/scripts/status.sh"

job='periodic-ci-openshift-lvm-operator-release-5.0-nightly-e2e-baremetalds-tnf-lvms-mno-qe-integration-tests'
printf '%s\n' "$job" > "$test_dir/jobs/tnf-lvms.txt"
printf '[{"JobName":"%s","JobURL":"https://prow.ci.openshift.org/view/gs/example"}]\n' "$job" \
    > "$test_dir/runs/demo/tnf/gangway_failed.json"

cat > "$test_dir/bin/curl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *'/finished.json') printf '%s\n' '{"result":"FAILURE"}' ;;
    *'/artifacts/e2e-baremetalds-tnf-lvms-mno-qe-integration-tests/lvms-tnf-mno-integration-test/artifacts/junit_results.xml')
        case "$TEST_STATUS_MODE" in
            failure) printf '%s\n' '<testsuite><testcase name="device selector"><failure message="capacity failed"/></testcase><testcase name="RapiDAST"><skipped/></testcase></testsuite>' ;;
            expected-skip|unexpected-skip) printf '%s\n' '<testsuite><testcase name="RapiDAST"><skipped/></testcase><testcase name="ordinary skip"><skipped/></testcase></testsuite>' ;;
        esac ;;
    *'/artifacts/e2e-baremetalds-tnf-lvms-mno-qe-integration-tests/baremetalds-two-node-fencing-lvms-mno-validate-results/artifacts/skip-summary.txt')
        if [[ "$TEST_STATUS_MODE" == unexpected-skip ]]; then
            printf '%s\n' 'passed=39 failed=0 skipped=2' 'EXPECTED SKIP RapiDAST' 'UNEXPECTED SKIP ordinary skip'
        else
            exit 22
        fi ;;
    *) exit 22 ;;
esac
EOF
chmod +x "$test_dir/bin/curl"
export TEST_STATUS_MODE
export PATH="$test_dir/bin:$PATH"

check_reason() {
    local mode="$1" expected="$2" output reason
    TEST_STATUS_MODE="$mode"
    if output=$("$test_dir/scripts/status.sh" tnf --run demo --failed --logs --json 2>&1); then
        echo "$mode unexpectedly reported a passing job: $output" >&2
        exit 1
    fi
    reason=$(printf '%s\n' "$output" | jq -r '.topologies.tnf.jobs[0].failure_reason')
    if [[ "$reason" != "$expected" ]]; then
        echo "$mode reported '$reason', expected '$expected'" >&2
        exit 1
    fi
    echo "$mode: OK"
}

check_reason failure 'device selector: capacity failed'
check_reason expected-skip 'unable to determine failure from JUnit; inspect Prow steps'
check_reason unexpected-skip 'Unexpected skip: ordinary skip'
