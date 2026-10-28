# GitHub recipes

Raw `gh` commands for projects that define no workflow commands of their own. Replace `<owner>`, `<repo>`, `<N>` and `<project-number>`. Every write is followed by a read-back.

## Issues

```bash
# Ready, unassigned tickets, oldest first
gh issue list --repo <owner>/<repo> --state open --label ready-for-agent \
  --search "no:assignee sort:created-asc" --json number,title,labels,milestone

# Everything about one ticket
gh issue view <N> --repo <owner>/<repo> --comments

# Open blockers (native issue dependencies)
gh api repos/<owner>/<repo>/issues/<N>/dependencies/blocked_by \
  --jq '.[] | select(.state == "open") | "#\(.number) \(.title)"'

# Claim
gh issue edit <N> --repo <owner>/<repo> --add-assignee @me

# Comment, tick criteria (edit the body), close
gh issue comment <N> --repo <owner>/<repo> --body-file <file>
gh issue view <N> --repo <owner>/<repo> --json body -q .body > <file>   # edit, then:
gh issue edit <N> --repo <owner>/<repo> --body-file <file>
```

## Projects board Status

Needs a token with the `project` scope (`gh auth refresh -s project`).

```bash
# Ids, once per session
PROJECT_ID=$(gh project view <project-number> --owner <owner> --format json -q .id)
gh project field-list <project-number> --owner <owner> --format json \
  -q '.fields[] | select(.name == "Status") | {id, options}'

# The board item for issue N
ITEM_ID=$(gh project item-list <project-number> --owner <owner> --format json --limit 500 \
  -q ".items[] | select(.content.number == <N>) | .id")

# Set Status, then read it back
gh project item-edit --project-id "$PROJECT_ID" --id "$ITEM_ID" \
  --field-id <status-field-id> --single-select-option-id <option-id>
gh project item-list <project-number> --owner <owner> --format json --limit 500 \
  -q ".items[] | select(.content.number == <N>) | .status"
```

If the board has workflows that set In review on a linked PR and Done on merge, let them; check the result instead of setting it twice.

## Pull requests

```bash
gh pr create --base <default-branch> --head <branch> --title "<title>" --body-file <file>
gh pr view <branch> --json number,url,state,mergeable,statusCheckRollup
gh pr checks <branch>          # once; prefer the host's PR monitor to polling
```
