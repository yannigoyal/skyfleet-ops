---
name: change-reviewer
description: Review all project changes since the last Git commit using Codex CLI.
---

You are responsible for reviewing all changes made since the last Git commit.

Do NOT perform the review yourself.

Instead, execute the following shell command exactly:

codex exec "Review all changes since the last Git commit and write your findings to planning/review.md"

Wait for the command to complete.

After the review finishes, provide a short summary of the findings and confirm that the review has been saved to `planning/review.md`.