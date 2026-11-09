// Regev's WhatsApp agent — Baileys server (same approach as Itay's adsend/baileys-server).
// Runs on Railway as a dumb relay: it holds the WhatsApp link, queues messages from the
// OWNER only, and sends replies. The "brain" is bridge.js on Regev's PC, which polls the
// inbox and answers with read-only access to the projects folder.
// Safety: default-deny. Messages from anyone except OWNER_NUMBER are dropped silently —
// never queued, never answered, never marked as read. The only group listened to is
// ALLOWED_GROUP_NAME ("הסוכנים"). There every owner message reaches every agent (each decides
// if it's in its area); everything else said there is kept only as conversation context. Statuses/channels are dropped.
import 'dotenv/config'
import express from 'express'
import { makeWASocket, DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion, downloadMediaMessage } from '@whiskeysockets/baileys'
import QRCode from 'qrcode'
import pino from 'pino'
import { mkdir, readdir, rm } from 'fs/promises'
import path from 'path'

const app = express()
app.use(express.json({ limit: '1mb' }))

// ── CORS: the connect page is a local file (origin "null"), so allow any origin.
// Every control endpoint is still protected by the shared secret below.
app.use((req, res, next) => {
  res.set('Access-Control-Allow-Origin', '*')
  res.set('Access-Control-Allow-Headers', 'Content-Type, x-api-secret')
  res.set('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
  if (req.method === 'OPTIONS') return res.sendStatus(204)
  next()
})

// ── AUTH: shared secret. Fail-closed if not configured. /health stays open for Railway.
const API_SECRET = process.env.AGENT_API_SECRET
app.use((req, res, next) => {
  if (req.path === '/health') return next()
  if (!API_SECRET) return res.status(503).json({ error: 'server misconfigured: AGENT_API_SECRET missing' })
  if (req.get('x-api-secret') !== API_SECRET) return res.status(401).json({ error: 'unauthorized' })
  next()
})

const SESSIONS_DIR = process.env.SESSIONS_DIR ?? './sessions'
const logger = pino({ level: 'warn' })

// The only number whose messages are relayed to the bridge (international format, digits only)
const OWNER_NUMBER = (process.env.OWNER_NUMBER ?? '').replace(/\D/g, '')

// sessionId → { socket, qr, status, phone }
const sessions = new Map()
// sessionId → [{ id, jid, text, ts }] — owner messages waiting for the bridge
const inboxes = new Map()
// sessionId → last time the bridge polled (ms)
const lastBridgePoll = new Map()
// sessionId → last time we told the owner the PC is offline (ms)
const lastOfflineNotice = new Map()
const BRIDGE_OFFLINE_MS = 90_000
const OFFLINE_NOTICE_EVERY_MS = 10 * 60_000
// IDs of messages the agent itself sent
const sentByAgent = new Set()
// Recently processed message IDs, to dedupe Baileys re-emits
const processedMessages = new Map()
const DEDUP_TTL_MS = 60_000

const debugLog = []
function dlog(line) {
  const stamped = `${new Date().toISOString()} ${line}`
  debugLog.push(stamped)
  if (debugLog.length > 200) debugLog.shift()
  console.log(stamped)
}

function isDuplicate(msgId) {
  if (!msgId) return false
  const now = Date.now()
  for (const [id, ts] of processedMessages) {
    if (now - ts > DEDUP_TTL_MS) processedMessages.delete(id)
  }
  if (processedMessages.has(msgId)) return true
  processedMessages.set(msgId, now)
  return false
}

const SESSION_ID_RE = /^[a-z0-9][a-z0-9-]{1,63}$/i

await mkdir(SESSIONS_DIR, { recursive: true })

async function startSession(sessionId) {
  const existing = sessions.get(sessionId)
  if (existing && existing.status !== 'disconnected') return

  const sessionDir = path.join(SESSIONS_DIR, sessionId)
  await mkdir(sessionDir, { recursive: true })
  const { state, saveCreds } = await useMultiFileAuthState(sessionDir)
  const { version } = await fetchLatestBaileysVersion()

  const sock = makeWASocket({ version, auth: state, logger, printQRInTerminal: false, markOnlineOnConnect: false })
  sock.__sessionId = sessionId
  sessions.set(sessionId, { socket: sock, qr: null, status: 'connecting', phone: null })

  sock.ev.on('creds.update', saveCreds)

  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    const session = sessions.get(sessionId) ?? {}
    dlog(`[${sessionId}] connection=${connection ?? '-'} qr=${qr ? 'yes' : 'no'} err=${lastDisconnect?.error?.message ?? 'none'}`)

    if (qr) {
      const qrImage = await QRCode.toDataURL(qr, { margin: 1, width: 320 })
      sessions.set(sessionId, { ...session, qr: qrImage, status: 'connecting' })
    }

    if (connection === 'open') {
      const phone = sock.user?.id?.split(':')[0] ?? null
      sessions.set(sessionId, { ...session, qr: null, status: 'connected', phone })
      dlog(`[${sessionId}] CONNECTED as ${phone}`)
    }

    if (connection === 'close') {
      const code = lastDisconnect?.error?.output?.statusCode
      const shouldReconnect = code !== DisconnectReason.loggedOut
      sessions.set(sessionId, { ...session, status: 'disconnected', qr: null })
      dlog(`[${sessionId}] DISCONNECTED code=${code} willReconnect=${shouldReconnect}`)
      if (shouldReconnect) {
        sessions.delete(sessionId)
        setTimeout(() => startSession(sessionId), 3000)
      } else {
        // Unlinked from the phone: credentials are dead. Wipe them so a fresh QR can be generated.
        await rm(sessionDir, { recursive: true, force: true }).catch(() => {})
        sessions.delete(sessionId)
        dlog(`[${sessionId}] dead credentials wiped after loggedOut`)
      }
    }
  })

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' || !OWNER_NUMBER) return
    for (const msg of messages) {
      // Anything this account sent (including our own replies) is never handled
      if (msg.key.fromMe || sentByAgent.has(msg.key.id)) continue
      const remoteJid = msg.key.remoteJid ?? ''
      const isGroup = remoteJid.endsWith('@g.us')
      // 1:1 chats + the one allowed group. Other groups, broadcasts, channels, statuses: dropped
      if (!isGroup && !remoteJid.endsWith('@s.whatsapp.net') && !remoteJid.endsWith('@lid')) continue
      // Group-only agents (Roni = Regev's BUSINESS number): private chats are never touched,
      // not even Regev's. No queue, no reply, no "offline" notice, not marked as read.
      if (!isGroup && GROUP_ONLY_SESSIONS.has(sessionId)) continue
      if (isGroup && !(await isAllowedGroup(sock, remoteJid))) continue

      // Real phone of the sender. With LID addressing WhatsApp hides it, so take it from
      // senderPn (1:1) / participantPn (group). If we can't prove who it is, it's not the owner.
      const rawSender = isGroup
        ? ((msg.key.participant ?? '').endsWith('@lid') ? (msg.key.participantPn ?? '') : (msg.key.participant ?? ''))
        : (remoteJid.endsWith('@lid') ? (msg.key.senderPn ?? '') : remoteJid)
      const senderPhone = userPart(rawSender)
      const inner = unwrap(msg.message)
      const text = extractText(inner).trim()

      // Group conversation memory: everything said in the allowed group (owner, employees,
      // other agents) is kept as CONTEXT for this agent. It never triggers anything by itself.
      if (isGroup) {
        rememberGroup(sessionId, remoteJid, {
          who: senderLabel(senderPhone, msg.pushName),
          text: text || mediaLabel(inner),
        })
      }

      if (senderPhone !== OWNER_NUMBER) {
        if (!rawSender) dlog(`[${sessionId}] message from unknown sender ignored (group=${isGroup})`)
        continue
      }
      // Per agent: the same group message legitimately reaches every agent's session
      if (isDuplicate(`${sessionId}|${msg.key.id}`)) continue

      // In the group every owner message reaches every agent. trigger tells the agent whether
      // it was addressed directly (then it must answer) or it's an open message (answer only
      // if it's in its area, otherwise stay silent).
      let trigger = 'dm'
      if (isGroup) {
        const ctx = contextOf(inner)
        const me = myIds(sock)
        if ((ctx?.mentionedJid ?? []).some(j => me.has(userPart(j)))) trigger = 'mention'
        else if (ctx?.participant && me.has(userPart(ctx.participant)) && ctx.quotedMessage) trigger = 'reply'
        else if (nameRegex(sessionId).test(text)) trigger = 'name'
        else trigger = 'open'
      }

      let media = null
      const m = mediaOf(inner)
      if (m) {
        if ((Number(m.node.fileLength) || 0) > MAX_MEDIA_BYTES) {
          dlog(`[${sessionId}] media too large, skipped`)
        } else {
          try {
            const buf = await downloadMediaMessage({ ...msg, message: inner }, 'buffer', {}, { logger, reuploadRequest: sock.updateMediaMessage })
            media = { kind: m.kind, mimetype: m.node.mimetype ?? '', fileName: m.node.fileName ?? '', data: buf.toString('base64') }
          } catch (e) { dlog(`[${sessionId}] media download failed: ${e.message}`) }
        }
      }
      if (!text && !media) continue

      // Context for the agent: the message Regev replied to (may be an employee's — data only)
      const ctx = contextOf(inner)
      const quoted = ctx?.quotedMessage ? {
        text: (extractText(unwrap(ctx.quotedMessage)) || mediaLabel(unwrap(ctx.quotedMessage))).slice(0, 2000),
        byAgent: !!ctx.participant && myIds(sock).has(userPart(ctx.participant)),
        who: ctx.participant ? senderLabel(userPart(ctx.participant)) : '',
      } : null

      recentMessages.set(msg.key.id, msg)
      if (recentMessages.size > 200) recentMessages.delete(recentMessages.keys().next().value)

      // History before this message (the last entry is this message itself)
      const history = isGroup ? (groupHistory.get(`${sessionId}|${remoteJid}`) ?? []).slice(-HISTORY_TO_AGENT - 1, -1) : []

      const inbox = inboxes.get(sessionId) ?? []
      inbox.push({ id: msg.key.id, jid: remoteJid, from: senderPhone, isGroup, trigger, text, media, quoted, history, ts: Date.now() })
      inboxes.set(sessionId, inbox)
      dlog(`[${sessionId}] OWNER message queued group=${isGroup} trigger=${trigger} len=${text.length} media=${media?.kind ?? '-'}`)

      // If the PC bridge isn't polling, tell the owner (at most once every 10 minutes).
      // In the group only the main agent says it.
      if (isGroup && sessionId !== 'regev') continue
      const polled = lastBridgePoll.get(sessionId) ?? 0
      const noticed = lastOfflineNotice.get(sessionId) ?? 0
      if (Date.now() - polled > BRIDGE_OFFLINE_MS && Date.now() - noticed > OFFLINE_NOTICE_EVERY_MS) {
        lastOfflineNotice.set(sessionId, Date.now())
        await sendText(sock, remoteJid, 'המחשב כרגע לא מחובר. ההודעה נשמרה ואענה כשהמחשב יעלה.').catch(() => {})
      }
    }
  })
}

// The only group any agent listens in (besides 1:1 chats with the owner)
const ALLOWED_GROUP_NAME = process.env.ALLOWED_GROUP_NAME ?? 'הסוכנים'
const MAX_MEDIA_BYTES = 25 * 1024 * 1024
// Known agent numbers, so the group history says who said what
const AGENT_PHONES = { '972559968359': 'רוני (מנכ"ל)', '972552510543': 'יניב' }
// sessionId|groupJid → last messages in the group (context only)
const groupHistory = new Map()
const HISTORY_KEEP = 40
const HISTORY_TO_AGENT = 25

function senderLabel(phone, pushName) {
  if (phone && phone === OWNER_NUMBER) return 'רגב'
  if (phone && AGENT_PHONES[phone]) return AGENT_PHONES[phone]
  return pushName ? `${pushName} (עובד)` : 'משתתף אחר'
}
function rememberGroup(sessionId, jid, entry) {
  if (!entry.text) return
  const key = `${sessionId}|${jid}`
  const h = groupHistory.get(key) ?? []
  h.push({ ...entry, text: String(entry.text).slice(0, 1500), ts: Date.now() })
  if (h.length > HISTORY_KEEP) h.splice(0, h.length - HISTORY_KEEP)
  groupHistory.set(key, h)
}
// Image / video / voice / document in the message, if any
function mediaOf(message) {
  if (!message) return null
  if (message.imageMessage) return { kind: 'image', node: message.imageMessage }
  if (message.videoMessage) return { kind: 'video', node: message.videoMessage }
  if (message.audioMessage) return { kind: 'audio', node: message.audioMessage }
  if (message.documentMessage) return { kind: 'document', node: message.documentMessage }
  return null
}
function mediaLabel(message) {
  const m = mediaOf(message)
  if (!m) return ''
  return { image: '[תמונה]', video: '[סרטון]', audio: '[הקלטה]', document: `[קובץ ${m.node.fileName ?? ''}]` }[m.kind]
}
// sessionId → the name that wakes that agent up in the group
const AGENT_NAMES = { regev: ['רוני', 'סוכן ראשי', 'הסוכן הראשי'], yaniv: ['יניב'] }
// Agents that work ONLY inside the allowed group and ignore every private chat
const GROUP_ONLY_SESSIONS = new Set(['regev'])
function nameRegex(sessionId) {
  const names = AGENT_NAMES[sessionId] ?? [sessionId]
  return new RegExp(`(^|[^\\p{L}])(${names.join('|')})(?=$|[^\\p{L}])`, 'u')
}
// Messages we may quote in replies (id → full Baileys message)
const recentMessages = new Map()
// group jid → { ok, ts }
const groupCache = new Map()

async function isAllowedGroup(sock, jid) {
  const c = groupCache.get(jid)
  if (c && Date.now() - c.ts < 10 * 60_000) return c.ok
  let ok = false
  try { ok = (await sock.groupMetadata(jid))?.subject?.trim() === ALLOWED_GROUP_NAME } catch {}
  groupCache.set(jid, { ok, ts: Date.now() })
  if (ok) dlog(`allowed group found: ${jid}`)
  return ok
}

// "972501234567:12@s.whatsapp.net" → "972501234567"
function userPart(jid) {
  return String(jid ?? '').split('@')[0].split(':')[0].replace(/\D/g, '')
}
// Every id this account is known by (phone + LID)
function myIds(sock) {
  const ids = new Set()
  for (const j of [sock.user?.id, sock.user?.lid, sock.authState?.creds?.me?.id, sock.authState?.creds?.me?.lid]) {
    const u = userPart(j); if (u) ids.add(u)
  }
  return ids
}

// Unwrap nested containers (ephemeral/viewOnce/edited)
function unwrap(message) {
  if (!message) return message
  for (const wrapper of ['ephemeralMessage', 'viewOnceMessage', 'viewOnceMessageV2', 'documentWithCaptionMessage', 'editedMessage']) {
    if (message[wrapper]?.message) return unwrap(message[wrapper].message)
  }
  return message
}
function contextOf(message) {
  if (!message) return null
  for (const v of Object.values(message)) if (v && typeof v === 'object' && v.contextInfo) return v.contextInfo
  return null
}

function extractText(message) {
  message = unwrap(message)
  if (!message) return ''
  return message.conversation
    ?? message.extendedTextMessage?.text
    ?? message.imageMessage?.caption
    ?? message.videoMessage?.caption
    ?? ''
}

async function sendText(sock, jid, text, quotedId) {
  const quoted = quotedId ? recentMessages.get(quotedId) : undefined
  const sent = await sock.sendMessage(jid, { text }, quoted ? { quoted } : undefined)
  if (jid.endsWith('@g.us') && sock.__sessionId) {
    rememberGroup(sock.__sessionId, jid, { who: AGENT_PHONES[userPart(sock.user?.id)] ?? 'אני', text })
  }
  if (sent?.key?.id) {
    sentByAgent.add(sent.key.id)
    if (sentByAgent.size > 500) sentByAgent.delete(sentByAgent.values().next().value)
  }
}

// ── REST API ─────────────────────────────────────────────
app.param('sessionId', (req, res, next, id) => {
  if (!SESSION_ID_RE.test(id)) return res.status(400).json({ error: 'bad session id' })
  next()
})

app.post('/session/:sessionId/start', async (req, res) => {
  const { sessionId } = req.params
  await startSession(sessionId)
  // Give Baileys a moment to produce the first QR
  for (let i = 0; i < 10 && !sessions.get(sessionId)?.qr && sessions.get(sessionId)?.status === 'connecting'; i++) {
    await new Promise(r => setTimeout(r, 500))
  }
  const s = sessions.get(sessionId)
  res.json({ status: s?.status ?? 'disconnected', phone: s?.phone ?? null, qr: s?.qr ?? null })
})

app.get('/session/:sessionId/status', (req, res) => {
  const s = sessions.get(req.params.sessionId)
  const polled = lastBridgePoll.get(req.params.sessionId) ?? 0
  const bridgeOnline = Date.now() - polled < BRIDGE_OFFLINE_MS
  if (!s) return res.json({ status: 'disconnected', bridgeOnline })
  res.json({ status: s.status, phone: s.phone, qr: s.qr, bridgeOnline })
})

// Bridge polls this: returns and clears the owner's pending messages
app.get('/session/:sessionId/inbox', (req, res) => {
  const { sessionId } = req.params
  lastBridgePoll.set(sessionId, Date.now())
  const items = inboxes.get(sessionId) ?? []
  inboxes.set(sessionId, [])
  res.json({ messages: items })
})

// Bridge tells the owner it's working on the answer
app.post('/session/:sessionId/typing', async (req, res) => {
  const s = sessions.get(req.params.sessionId)
  const { jid, on } = req.body ?? {}
  if (s?.socket && s.status === 'connected' && jid) {
    try { await s.socket.sendPresenceUpdate(on === false ? 'paused' : 'composing', jid) } catch {}
  }
  res.json({ ok: true })
})

// Send a message. Use `jid` to reply in the chat a message came from, or `to` with a phone
// number in local (05X...) or international (9725X...) format.
app.post('/session/:sessionId/send', async (req, res) => {
  const s = sessions.get(req.params.sessionId)
  if (!s?.socket || s.status !== 'connected') return res.status(409).json({ ok: false, error: 'not connected' })
  const { to, jid, text, replyTo } = req.body ?? {}
  let target = jid
  if (!target) {
    let phone = String(to ?? '').replace(/\D/g, '')
    if (phone.startsWith('0')) phone = '972' + phone.slice(1)
    if (phone.length >= 11) target = `${phone}@s.whatsapp.net`
  }
  if (!target || !text) return res.status(400).json({ ok: false, error: 'to/jid and text required' })
  await sendText(s.socket, target, String(text), replyTo)
  dlog(`[${req.params.sessionId}] SEND len=${String(text).length}`)
  res.json({ ok: true })
})

// Groups this agent is a member of: [{ jid, subject, size }]
app.get('/session/:sessionId/groups', async (req, res) => {
  const s = sessions.get(req.params.sessionId)
  if (!s?.socket || s.status !== 'connected') return res.status(409).json({ ok: false, error: 'not connected' })
  try {
    const all = await s.socket.groupFetchAllParticipating()
    res.json({ groups: Object.values(all).map(g => ({ jid: g.id, subject: g.subject, size: g.participants?.length ?? 0 })) })
  } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

// The display name stored in this session's credentials
app.get('/session/:sessionId/me', (req, res) => {
  const s = sessions.get(req.params.sessionId)
  const me = s?.socket?.authState?.creds?.me ?? {}
  res.json({ name: me.name ?? null, verifiedName: me.verifiedName ?? null, userName: s?.socket?.user?.name ?? null })
})

// Set this agent's WhatsApp display name. Body: { name }
// ⚠️ Never call this for an agent without Regev's explicit request: 0559968359 is his BUSINESS number.
app.post('/session/:sessionId/profile-name', async (req, res) => {
  const s = sessions.get(req.params.sessionId)
  if (!s?.socket || s.status !== 'connected') return res.status(409).json({ ok: false, error: 'not connected' })
  const name = String(req.body?.name ?? '').trim().slice(0, 25)
  if (!name) return res.status(400).json({ ok: false, error: 'name required' })
  try {
    await s.socket.updateProfileName(name)
    dlog(`[${req.params.sessionId}] profile name updated`)
    res.json({ ok: true })
  } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

// Set this agent's WhatsApp profile picture. Body: { image: "<base64 jpg/png>" }
app.post('/session/:sessionId/profile-picture', express.json({ limit: '15mb' }), async (req, res) => {
  const s = sessions.get(req.params.sessionId)
  if (!s?.socket || s.status !== 'connected') return res.status(409).json({ ok: false, error: 'not connected' })
  const image = req.body?.image
  if (!image) return res.status(400).json({ ok: false, error: 'image required' })
  // { group: true } → the picture of the allowed group ("הסוכנים") instead of the number's own
  let target = s.socket.user.id
  if (req.body?.group) {
    const all = await s.socket.groupFetchAllParticipating().catch(() => ({}))
    const g = Object.values(all).find(x => x.subject?.trim() === ALLOWED_GROUP_NAME)
    if (!g) return res.status(404).json({ ok: false, error: 'allowed group not found' })
    target = g.id
  }
  try {
    await s.socket.updateProfilePicture(target, Buffer.from(image, 'base64'))
    dlog(`[${req.params.sessionId}] profile picture updated`)
    res.json({ ok: true })
  } catch (e) {
    dlog(`[${req.params.sessionId}] profile picture failed: ${e.message}`)
    res.status(500).json({ ok: false, error: e.message })
  }
})

app.delete('/session/:sessionId', async (req, res) => {
  const { sessionId } = req.params
  const s = sessions.get(sessionId)
  if (s?.socket) {
    try { await s.socket.logout() } catch {}
    try { s.socket.end() } catch {}
  }
  sessions.delete(sessionId)
  await rm(path.join(SESSIONS_DIR, sessionId), { recursive: true, force: true }).catch(() => {})
  dlog(`[${sessionId}] disconnected by request, auth wiped`)
  res.json({ ok: true })
})

app.get('/health', (_, res) => res.json({ ok: true, sessions: sessions.size }))
app.get('/debug/last', (_, res) => res.type('text/plain').send(debugLog.join('\n')))

// Re-connect every session whose credentials exist on the persistent volume
async function restoreSessions() {
  try {
    const dirs = await readdir(SESSIONS_DIR, { withFileTypes: true })
    const ids = dirs.filter(d => d.isDirectory() && SESSION_ID_RE.test(d.name)).map(d => d.name)
    dlog(`startup: restoring ${ids.length} session(s), owner=${OWNER_NUMBER ? 'set' : 'MISSING'}`)
    for (const id of ids) await startSession(id).catch(e => dlog(`startup: ${id} failed: ${e.message}`))
  } catch (e) {
    dlog(`startup: readdir failed: ${e.message}`)
  }
}

const PORT = process.env.PORT ?? 3001
app.listen(PORT, async () => {
  console.log(`WhatsApp agent running on :${PORT}`)
  await restoreSessions()
})
