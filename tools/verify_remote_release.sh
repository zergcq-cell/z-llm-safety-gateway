#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
repository="${2:-zergcq-cell/z-llm-safety-gateway}"
head_sha="${3:-$(git rev-parse HEAD)}"
version="v0.2.2"

if [[ "$mode" != "annotations" && "$mode" != "pre-tag" && "$mode" != "release" ]]; then
  echo "usage: $0 {annotations|pre-tag|release} [owner/repository] [head-sha]" >&2
  exit 2
fi
if [[ ! "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "invalid repository" >&2
  exit 2
fi
if [[ ! "$head_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "invalid head SHA" >&2
  exit 2
fi

temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT

latest_successful_run() {
  local workflow="$1"
  local event="$2"
  local output="$temporary_directory/${workflow}-${event}.json"
  gh run list \
    --repo "$repository" \
    --workflow "$workflow" \
    --event "$event" \
    --commit "$head_sha" \
    --limit 1 \
    --json databaseId,conclusion,headSha \
    > "$output"
  jq -er --arg head "$head_sha" \
    'if length == 1 and .[0].headSha == $head and .[0].conclusion == "success"
     then .[0].databaseId
     else error("mandatory workflow run is missing or not successful")
     end' \
    "$output"
}

if [[ "$mode" == "pre-tag" ]]; then
  ci_run_id="$(latest_successful_run CI push)"
  dry_run_id="$(latest_successful_run Release workflow_dispatch)"

  set +e
  gh api --include "repos/$repository/releases/tags/$version" \
    > "$temporary_directory/pre-tag-release.txt" 2>&1
  release_exit=$?
  set -e
  test "$release_exit" -ne 0
  grep -Eq '^HTTP/[0-9.]+ 404' "$temporary_directory/pre-tag-release.txt"

  tag_ref="$(git ls-remote "https://github.com/$repository.git" "refs/tags/$version")"
  test -z "$tag_ref"
  jq -n \
    --arg repository "$repository" \
    --arg head_sha "$head_sha" \
    --argjson ci_run_id "$ci_run_id" \
    --argjson dry_run_id "$dry_run_id" \
    '{repository:$repository,head_sha:$head_sha,ci_run_id:$ci_run_id,dry_run_id:$dry_run_id,release_status:404,tag_absent:true}'
  exit 0
fi

if [[ "$mode" == "annotations" ]]; then
  run_ids=(
    "$(latest_successful_run CI push)"
    "$(latest_successful_run Release workflow_dispatch)"
    "$(latest_successful_run Release push)"
  )
  for run_id in "${run_ids[@]}"; do
    check_ids_file="$temporary_directory/check-ids-$run_id.txt"
    gh run view "$run_id" \
      --repo "$repository" \
      --json jobs \
      --jq '.jobs[].databaseId' \
      > "$check_ids_file"
    test -s "$check_ids_file"
    if grep -Evq '^[0-9]+$' "$check_ids_file"; then
      echo "invalid check-run ID for workflow run $run_id" >&2
      exit 1
    fi
    while IFS= read -r check_id; do
      gh api --paginate \
        "repos/$repository/check-runs/$check_id/annotations" \
        --jq '.[].message' \
        > "$temporary_directory/annotations-$check_id.txt"
      if grep -Eiq 'Node\.js 20|node20' "$temporary_directory/annotations-$check_id.txt"; then
        echo "Node.js 20 annotation found in check run $check_id" >&2
        exit 1
      fi
    done < "$check_ids_file"
  done
  exit 0
fi

tag_run_id="$(latest_successful_run Release push)"
gh run download "$tag_run_id" \
  --repo "$repository" \
  --name distributions \
  --dir "$temporary_directory/dist"
gh run download "$tag_run_id" \
  --repo "$repository" \
  --name "release-evidence-$version" \
  --dir "$temporary_directory/evidence"

python tools/release_checks.py asset-digests \
  --version "$version" \
  --dist-dir "$temporary_directory/dist" \
  --output "$temporary_directory/expected-digests.json"
gh api "repos/$repository/releases/tags/$version" \
  --jq '{tagName:.tag_name,body,isDraft:.draft,isPrerelease:.prerelease,url:.html_url,assets:[.assets[]|{name,state,size,digest}]}' \
  > "$temporary_directory/release.json"

remote_refs="$(
  git ls-remote "https://github.com/$repository.git" \
    "refs/tags/$version" \
    "refs/tags/$version^{}" \
    refs/tags/v0.2.0 \
    "refs/tags/v0.2.0^{}" \
    refs/tags/v0.2.1 \
    "refs/tags/v0.2.1^{}"
)"
tag_object="$(printf '%s\n' "$remote_refs" | awk -v ref="refs/tags/$version" '$2 == ref {print $1}')"
peeled_commit="$(printf '%s\n' "$remote_refs" | awk -v ref="refs/tags/$version^{}" '$2 == ref {print $1}')"
jq -n \
  --arg tag_object "$tag_object" \
  --arg peeled_commit "$peeled_commit" \
  '{tag_object:$tag_object,peeled_commit:$peeled_commit}' \
  > "$temporary_directory/refs.json"

python tools/release_checks.py github-release \
  --version "$version" \
  --input "$temporary_directory/release.json" \
  --expected-state public \
  --expected-digests "$temporary_directory/expected-digests.json" \
  --refs-input "$temporary_directory/refs.json" \
  --expected-sha "$head_sha"

evidence="$temporary_directory/evidence/release-evidence.json"
test "$(jq -r '.workflow.run_id' "$evidence")" = "$tag_run_id"
jq '.workflow' "$evidence" > "$temporary_directory/workflow.json"
verified_at="$(jq -r '.verified_at' "$evidence")"
python tools/release_checks.py evidence \
  --version "$version" \
  --release-input "$temporary_directory/release.json" \
  --refs-input "$temporary_directory/refs.json" \
  --workflow-input "$temporary_directory/workflow.json" \
  --expected-sha "$head_sha" \
  --expected-digests "$temporary_directory/expected-digests.json" \
  --verified-at "$verified_at" \
  --output "$temporary_directory/expected-evidence.json"
cmp "$evidence" "$temporary_directory/expected-evidence.json"

test "$(printf '%s\n' "$remote_refs" | awk '$2 == "refs/tags/v0.2.0" {print $1}')" = \
  "dae034025cc7f68d13ef7b9b3ba3f1b1eca35411"
test "$(printf '%s\n' "$remote_refs" | awk '$2 == "refs/tags/v0.2.0^{}" {print $1}')" = \
  "d67d573b0e38691707e70e64a7ec1a431ca1f545"
test "$(printf '%s\n' "$remote_refs" | awk '$2 == "refs/tags/v0.2.1" {print $1}')" = \
  "34de8b28c58d19175631f2384561bf4f806f5d17"
test "$(printf '%s\n' "$remote_refs" | awk '$2 == "refs/tags/v0.2.1^{}" {print $1}')" = \
  "c8daffcef87326c377aa4abd945a46a6455da1eb"

set +e
gh api --include "repos/$repository/releases/tags/v0.2.0" \
  > "$temporary_directory/v0.2.0-release.txt" 2>&1
v020_exit=$?
set -e
test "$v020_exit" -ne 0
grep -Eq '^HTTP/[0-9.]+ 404' "$temporary_directory/v0.2.0-release.txt"
gh api "repos/$repository/releases/tags/v0.2.1" \
  --jq '.tag_name == "v0.2.1" and .draft == false and .prerelease == false' \
  | grep -Fxq true
