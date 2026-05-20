# Autoniix — GitHub Issue Filters (Jira-style)

All issues follow the `[ATNX-{number}]` title prefix and carry exactly one `type:*` label.  
Click a link to open the pre-filtered GitHub Issues board.

---

## By Type

| Type | Label | Filter |
|---|---|---|
| 🟣 Epics | `type:epic` | [Open Epics](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Atype%3Aepic) |
| 🔵 Stories | `type:story` | [Open Stories](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Atype%3Astory) |
| 🟢 Tasks | `type:task` | [Open Tasks](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Atype%3Atask) |
| 🩵 Subtasks | `type:subtask` | [Open Subtasks](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Atype%3Asubtask) |
| 🔴 Bugs | `type:bug` | [Open Bugs](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Atype%3Abug) |

---

## By Lifecycle Stage

| Stage | Filter |
|---|---|
| Ready for Dev | [ready-for-dev](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Aready-for-dev) |
| In Progress | [in-progress](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Ain-progress) |
| Dev Done | [dev-done](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Adev-done) |
| In QA | [in-qa](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Ain-qa) |
| QA Verified | [qa-verified](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Aqa-verified) |
| Ready to Deploy | [ready-to-deploy](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Aready-to-deploy) |
| In Prod | [in-prod](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Ain-prod) |

---

## Combined Filters (Power Queries)

| Query | Link |
|---|---|
| All open critical stories | [link](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Atype%3Astory+label%3Apriority%3Acritical) |
| All MVP stories ready for dev | [link](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Atype%3Astory+label%3Aready-for-dev+milestone%3A%22Autoniix+MVP%22) |
| All open bugs | [link](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+label%3Atype%3Abug) |
| All closed issues | [link](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aclosed) |
| Everything in Epic #40 (Provider Config) | [link](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+%2240+Provider%22) |
| Everything in Epic #41 (Video Pipeline) | [link](https://github.com/saurabhrawat-gh/Autoniix/issues?q=is%3Aopen+%2241+Video%22) |

---

## Label Colour Reference

| Label | Hex | Purpose |
|---|---|---|
| `type:epic` | `#7C3AED` 🟣 | Large feature container |
| `type:story` | `#2563EB` 🔵 | User story |
| `type:task` | `#059669` 🟢 | Implementation task / test plan |
| `type:subtask` | `#34D399` 🩵 | Sub-task nested under story/task |
| `type:bug` | `#DC2626` 🔴 | Defect / regression |

---

*Labels are created / kept in sync by `scripts/setup_jira_style.py`.*
