# Foundation validation

Validated locally on October 9, 2026 with Python 3.13 and Node 24.4.1. The repository's GitHub workflow also validates Python 3.11 on Linux and Node 24 without provider keys.

| Check | Local outcome |
| --- | --- |
| Backend package/install/import | PASS |
| Live `GET /api/health` | PASS: `{"status":"ok","service":"proofloop"}` |
| Backend tests | PASS: 20 tests, no warnings |
| Ruff lint and formatting | PASS: 28 Python files formatted |
| Generated JSON/OpenAPI contracts | PASS: current, fixture/event schemas validated |
| `npm ci` | PASS: clean install, 0 reported audit vulnerabilities |
| Frontend ESLint | PASS |
| TypeScript and production build | PASS: 22 modules, approximately 71 KB gzip JavaScript |
| Browser health flow | PASS: connected state and connection refresh |
| Browser unavailable-backend handling | PASS: unavailable status and error rendered, fixture preview preserved |
| Browser console before outage test | No errors or warnings |
| `.env.example` | Empty credential placeholders; no real credentials |
| Git ignore checks | Credentials, venv, dependencies, run data, disposable workspaces, generated reports ignored; `.env.example` tracked |

Initial checks caught a contract-test path error and deprecated lint/test dependencies. These were fixed before publication. No scanning, inference, attack execution, or sponsor API request was made. Backend scaffold tests are not security verification tests.

Inspect current remote state and CI with:

```sh
gh repo view nbobby07/proofloop --json url,visibility,defaultBranchRef
git ls-remote --heads origin main feat/security-engine feat/product-dashboard
gh run list --workflow ci.yml
```

The setup handoff records the initial commit hash, remote branch checks, final CI result, and any branch-protection limitation. Provider credentials, collaborator access, team contacts, and submission video remain manual setup. The full tracked directory inventory is in `REPOSITORY-TREE.txt`.
