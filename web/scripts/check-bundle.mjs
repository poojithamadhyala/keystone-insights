// Fail if the built web bundle contains anything that looks like a secret or a server-side
// variable name. `npm run build && npm run check-bundle`; runs in CI. Keys must stay server-side:
// the browser only ever gets VITE_API_URL.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const DIST = process.argv[2] ?? 'dist'
const PATTERNS = [
  /sk-ant-[A-Za-z0-9_-]{20,}/, // Anthropic key
  /pcsk_[A-Za-z0-9_]{20,}/, // Pinecone key
  /hooks\.slack\.com\/services\//, // Slack webhook
  /postgres(?:ql)?:\/\/[^\s"']+@/, // database URL with credentials
  /\b(?:ANTHROPIC_API_KEY|PINECONE_API_KEY|SLACK_WEBHOOK_URL|DIGEST_RUN_TOKEN|DATABASE_URL)\b/,
]

function files(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f)
    return statSync(p).isDirectory() ? files(p) : [p]
  })
}

const hits = []
for (const file of files(DIST)) {
  const text = readFileSync(file, 'utf8')
  for (const re of PATTERNS) if (re.test(text)) hits.push(`${file}: matches ${re}`)
}
if (hits.length) {
  console.error('Possible secret in the web bundle:\n' + hits.join('\n'))
  process.exit(1)
}
console.log(`bundle scan: clean (${files(DIST).length} files)`)
