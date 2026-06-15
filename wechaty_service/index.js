const express = require('express')
const QRCode = require('qrcode')
const { Wechaty } = require('wechaty')

const PORT = Number(process.env.WECHATY_SERVICE_PORT || 8788)
const BACKEND_INGEST_URL = process.env.WECHAT_BACKEND_INGEST_URL || 'http://127.0.0.1:5000/api/wechat/ingest'
const INGEST_SECRET = process.env.WECHAT_INGEST_SECRET || ''

if (!process.env.WECHATY_PUPPET) process.env.WECHATY_PUPPET = 'wechaty-puppet-service'

let bot = null
let starting = null
let loggedIn = false
let nickname = ''
let qrBase64 = ''
let qrStatus = ''
let lastError = ''

let qrWaiters = []

async function waitForQr(timeoutMs) {
  if (qrBase64) return qrBase64
  return await new Promise((resolve) => {
    const timer = setTimeout(() => {
      qrWaiters = qrWaiters.filter((w) => w.resolve !== resolve)
      resolve('')
    }, timeoutMs)
    qrWaiters.push({
      resolve: (val) => {
        clearTimeout(timer)
        resolve(val)
      },
    })
  })
}

async function notifyQrWaiters() {
  const waiters = qrWaiters
  qrWaiters = []
  for (const w of waiters) w.resolve(qrBase64)
}

async function postIngest(payload) {
  try {
    const headers = { 'Content-Type': 'application/json' }
    if (INGEST_SECRET) headers['X-Wechat-Ingest-Secret'] = INGEST_SECRET
    await fetch(BACKEND_INGEST_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    })
  } catch {
  }
}

async function ensureBot() {
  if (bot) return bot
  if (starting) return await starting

  starting = (async () => {
    const token = process.env.WECHATY_PUPPET_SERVICE_TOKEN || process.env.TOKEN || process.env.token || ''
    if (!token) {
      lastError = 'missing WECHATY_PUPPET_SERVICE_TOKEN'
      throw new Error(lastError)
    }

    bot = new Wechaty({ name: 'data-extraction-wechaty' })

    bot.on('scan', async (qrcode, status) => {
      qrStatus = String(status)
      try {
        const dataUrl = await QRCode.toDataURL(qrcode)
        qrBase64 = dataUrl.replace(/^data:image\/png;base64,/, '')
        await notifyQrWaiters()
      } catch (e) {
        lastError = String(e && e.message ? e.message : e)
      }
    })

    bot.on('login', async (user) => {
      loggedIn = true
      nickname = user && user.name ? user.name() || user.name : ''
      qrBase64 = ''
      qrStatus = ''
      lastError = ''
    })

    bot.on('logout', async () => {
      loggedIn = false
      nickname = ''
    })

    bot.on('error', async (e) => {
      lastError = String(e && e.message ? e.message : e)
    })

    bot.on('message', async (message) => {
      try {
        const text = (await message.text()) || ''
        if (!text) return

        const talker = message.talker()
        const room = message.room()

        const isGroup = !!room
        const senderName = talker && talker.name ? talker.name() || talker.name : ''
        const senderUsername = talker && talker.id ? talker.id : ''

        let chatName = senderName
        let chatUsername = senderUsername
        if (room) {
          chatName = (await room.topic()) || ''
          chatUsername = room.id || ''
        }

        const ts = message.date ? message.date() : new Date()

        await postIngest({
          msg_id: message.id || `${Date.now()}-${Math.random()}`,
          msg_type: String(message.type ? message.type() : 'Text'),
          content: text,
          sender_name: senderName,
          sender_username: senderUsername,
          chat_name: chatName,
          chat_username: chatUsername,
          is_group: isGroup,
          timestamp: ts instanceof Date ? ts.toISOString() : new Date().toISOString(),
        })
      } catch {
      }
    })

    await bot.start()
    return bot
  })()

  try {
    return await starting
  } finally {
    starting = null
  }
}

async function stopBot() {
  try {
    if (bot) await bot.stop()
  } catch {
  }
  bot = null
  loggedIn = false
  nickname = ''
  qrBase64 = ''
  qrStatus = ''
  lastError = ''
}

const app = express()
app.use(express.json({ limit: '2mb' }))

app.get('/status', async (req, res) => {
  res.json({ success: true, logged_in: loggedIn, nickname, qr_status: qrStatus, error: lastError || '' })
})

app.post('/login', async (req, res) => {
  if (loggedIn) return res.json({ success: false, error: 'already logged in' })
  try {
    await ensureBot()
    const qr = await waitForQr(30000)
    if (!qr) return res.json({ success: false, error: lastError || 'qr code not ready' })
    res.json({ success: true, qr_code: qr })
  } catch (e) {
    res.json({ success: false, error: String(e && e.message ? e.message : e) })
  }
})

app.post('/logout', async (req, res) => {
  await stopBot()
  res.json({ success: true })
})

app.listen(PORT, () => {
  process.stdout.write(`wechaty-service listening on http://127.0.0.1:${PORT}\n`)
})
