import { defineConfig, loadEnv, type HtmlTagDescriptor, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'node:fs'
import path from 'node:path'

import siteConfiguration from './.figma/make/site.json' with { type: 'json' }


// Vite config — https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // .figma/make/deploy-preview passes `--mode development` for cached-preview builds.
  const emitSourcemaps = mode === 'development'

  return {
    base: process.env.FIGMA_PUBLIC_URL ? `${process.env.FIGMA_PUBLIC_URL}/` : '/',
    build: {
      sourcemap: emitSourcemaps ? 'inline' : false,
      minify: !emitSourcemaps,
    },
    plugins: [
react(),
      tailwindcss(),
      figmaSiteConfiguration(siteConfiguration),
      figmaErrorOverlayReplay(),
      figmaReactRefreshBoundaryFallback(),
      figmaMakeKitPlugin({ storiesGlob: '/src/**/*.stories.{ts,tsx,js,jsx}' }),
      figmaLinkedPackageSourcemaps(),
      nodemailerInvitePlugin(env),
    ],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, './src'),
      },
    },
    server: {
      host: process.env.FIGMA_DEV_SERVER_HOST || 'localhost',
      port: parseInt(process.env.PORT || '5173'),
      strictPort: true,
      watch: {
        ignored: [
          '**/.figma/**',
        ],
      },
    },
    preview: {
      host: process.env.FIGMA_DEV_SERVER_HOST || 'localhost',
      port: parseInt(process.env.PORT || '5173'),
    },
  }
})

type FigmaSiteConfiguration = {
  title?: string
  description?: string
  language?: string
  robots?: {
    index?: boolean
  }
  icons?: {
    icon?: string
  }
  openGraph?: {
    image?: string
  }
  analytics?: {
    googleAnalyticsId?: string
  }
  customScripts?: {
    headStart?: string
    headEnd?: string
    bodyStart?: string
    bodyEnd?: string
  }
  accessibility?: {
    addBypassLinks?: boolean
  }
}

/** Applies /.figma/make/site.json to the generated document shell. */
function figmaSiteConfiguration(config: FigmaSiteConfiguration): Plugin {
  function sanitizeHtmlValue(value: string | undefined): string {
    return value?.replace(/[^a-zA-Z0-9_-]/g, '') || ''
  }
  function escapeHtmlText(value: string): string {
    return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }
  function replaceHtmlCommentSlot(html: string, slotName: string, content: string): string {
    return html.replace(`<!-- ${slotName} -->`, content)
  }

  const title = config.title ?? "Figma Make App"
  const description = config.description ?? ''
  // Imported HTML keeps its own favicon; new Makes default to the Make product icon.
  const favicon = config.icons?.icon ?? '/favicon.svg'
  const socialImage = config.openGraph?.image ?? ''
  const language = sanitizeHtmlValue(config.language) || 'en'
  const googleAnalyticsId = sanitizeHtmlValue(config.analytics?.googleAnalyticsId)
  const headStart = config.customScripts?.headStart ?? ''
  const headEnd = config.customScripts?.headEnd ?? ''
  const bodyStart = config.customScripts?.bodyStart ?? ''
  const bodyEnd = config.customScripts?.bodyEnd ?? ''
  const robotsTxt = config.robots?.index === false ? 'User-agent: *\nDisallow: /\n' : ''

  return {
    name: 'figma-site-configuration',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (!robotsTxt || req.url?.split('?')[0] !== '/robots.txt') return next()

        res.setHeader('Content-Type', 'text/plain; charset=utf-8')
        res.end(robotsTxt)
      })
    },
    generateBundle() {
      if (!robotsTxt) return

      this.emitFile({
        type: 'asset',
        fileName: 'robots.txt',
        source: robotsTxt,
      })
    },
    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        let result = html
        result = replaceHtmlCommentSlot(result, 'figma:lang', language)
        result = replaceHtmlCommentSlot(result, 'figma:title', escapeHtmlText(title))
        result = replaceHtmlCommentSlot(result, 'figma:head-start', headStart)
        result = replaceHtmlCommentSlot(result, 'figma:head-end', headEnd)
        result = replaceHtmlCommentSlot(result, 'figma:body-start', bodyStart)
        result = replaceHtmlCommentSlot(result, 'figma:body-end', bodyEnd)

        const tags: HtmlTagDescriptor[] = []
        if (description) {
          tags.push({ tag: 'meta', attrs: { name: 'description', content: description }, injectTo: 'head' })
        }
        if (config.robots?.index === false) {
          tags.push({ tag: 'meta', attrs: { name: 'robots', content: 'noindex, nofollow' }, injectTo: 'head' })
        }
        if (favicon) {
          tags.push({ tag: 'link', attrs: { rel: 'icon', href: favicon }, injectTo: 'head' })
        }
        if (title) {
          tags.push({ tag: 'meta', attrs: { property: 'og:title', content: title }, injectTo: 'head' })
        }
        if (description) {
          tags.push({ tag: 'meta', attrs: { property: 'og:description', content: description }, injectTo: 'head' })
        }
        if (socialImage) {
          tags.push(
            { tag: 'meta', attrs: { property: 'og:image', content: socialImage }, injectTo: 'head' },
            { tag: 'meta', attrs: { name: 'twitter:card', content: 'summary_large_image' }, injectTo: 'head' },
            { tag: 'meta', attrs: { name: 'twitter:image', content: socialImage }, injectTo: 'head' },
          )
        }

        if (googleAnalyticsId) {
          tags.push(
            {
              tag: 'script',
              attrs: {
                async: true,
                src: `https://www.googletagmanager.com/gtag/js?id=${googleAnalyticsId}`,
              },
              injectTo: 'head',
            },
            {
              tag: 'script',
              children: `
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', ${JSON.stringify(googleAnalyticsId)});
`,
              injectTo: 'head',
            },
          )
        }

        if (config.accessibility?.addBypassLinks) {
          tags.push(
            {
              tag: 'style',
              children: `
  .figma-bypass-link {
    position: fixed;
    top: 8px;
    left: 8px;
    z-index: 2147483647;
    transform: translateY(-150%);
    border-radius: 6px;
    background: #111827;
    color: #fff;
    padding: 8px 12px;
    font: 600 14px/1.2 system-ui, sans-serif;
    text-decoration: none;
  }
  .figma-bypass-link:focus {
    transform: translateY(0);
  }
`,
              injectTo: 'head',
            },
            {
              tag: 'a',
              attrs: { class: 'figma-bypass-link', href: '#root' },
              children: 'Skip to content',
              injectTo: 'body-prepend',
            },
          )
        }

        return {
          html: result,
          tags,
        }
      },
    },
  }
}

/**
 * Replay the most recent build error to clients that connect after
 * it was first broadcast. Vite buffers an error payload only while
 * no clients are connected and clears the buffer on the first
 * reconnect (see `bufferedMessage` in `createWebSocketServer`), so
 * if the preview iframe reloads after Vite already delivered an
 * error to a live socket, the new socket misses the payload and
 * the overlay stays hidden even though the build is still broken.
 * We intercept `ws.send` to remember the latest error and replay
 * it on every new connection; the cache clears on a successful
 * `update` or `full-reload` so a stale overlay can't survive a
 * fixed build.
 */
function figmaErrorOverlayReplay(): Plugin {
  return {
    name: 'figma-error-overlay-replay',
    apply: 'serve',
    configureServer(server) {
      let lastError: object | null = null

      const origSend = server.ws.send.bind(server.ws) as (...args: any[]) => void
      server.ws.send = ((...args: any[]) => {
        const payload = args[0]
        if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
          const type = (payload as { type?: string }).type
          if (type === 'error') {
            lastError = payload as object
          } else if (type === 'update' || type === 'full-reload') {
            lastError = null
          }
        }
        return origSend(...args)
      }) as typeof server.ws.send

      server.ws.on('connection', (socket) => {
        if (lastError !== null) {
          socket.send(JSON.stringify(lastError))
        }
      })
    },
  }
}

/**
 * Reload when a module that previously defined a React Refresh boundary stops
 * defining one. This happens when an agent moves a component into a new file
 * and replaces the old module with a re-export:
 *
 *   export { default } from './app/App'
 *
 * Vite otherwise accepts the update using the previous module's HMR boundary,
 * but the re-export-only transform no longer registers a replacement for the
 * mounted component family. React reports a successful refresh while leaving
 * the old tree mounted until the page is reloaded.
 */
function figmaReactRefreshBoundaryFallback(): Plugin {
  type ModuleNode = import('vite').ModuleNode
  const hadRefreshBoundary = new Map<string, boolean>()
  const lostRefreshBoundaries = new Set<string>()
  let sendFullReload: (() => void) | null = null

  return {
    name: 'figma-react-refresh-boundary-fallback',
    apply: 'serve',
    enforce: 'post',
    configureServer(server) {
      sendFullReload = () => server.ws.send({ type: 'full-reload', path: '*' })
    },
    handleHotUpdate({ modules, server, timestamp }) {
      if (lostRefreshBoundaries.size === 0) return

      const visited = new Set<ModuleNode>()
      const pending = [...modules]
      while (pending.length > 0) {
        const current = pending.pop()
        if (!current || visited.has(current)) continue
        visited.add(current)

        const moduleId = current.id?.split('?')[0]
        if (moduleId && lostRefreshBoundaries.has(moduleId)) {
          const invalidated = new Set<ModuleNode>()
          for (const updatedModule of modules) {
            server.moduleGraph.invalidateModule(updatedModule, invalidated, timestamp, true)
          }
          sendFullReload?.()
          return []
        }

        pending.push(...current.importers)
      }
    },
    transform(code, id) {
      if (!/\.[jt]sx?(?:\?|$)/.test(id) || id.includes('/node_modules/')) return null

      const moduleId = id.split('?')[0] ?? id
      const hasRefreshBoundary = code.includes('registerExportsForReactRefresh')
      const previousHadRefreshBoundary = hadRefreshBoundary.get(moduleId)
      hadRefreshBoundary.set(moduleId, hasRefreshBoundary)

      if (hasRefreshBoundary) lostRefreshBoundaries.delete(moduleId)
      if (previousHadRefreshBoundary && !hasRefreshBoundary) {
        lostRefreshBoundaries.add(moduleId)
        queueMicrotask(() => sendFullReload?.())
      }

      return null
    },
  }
}

/**
 * Serves a blank render-target page at /.figma/make/kit.html that
 * the Figma preview script drives directly. The page exposes a
 * registry of every file matching `storiesGlob` on
 * window.__FIGMA__.stories so the design surface can dynamically
 * import + mount each entry into its own grid view.
 *
 * Dev-only: `apply: 'serve'` gates the plugin to `vite dev`. Prod
 * builds (`vite build`) skip it entirely so the route doesn't leak
 * into shipped bundles.
 */
function figmaMakeKitPlugin(options: { storiesGlob: string | string[] }): Plugin {
  const storiesGlob = Array.isArray(options.storiesGlob) ? options.storiesGlob : [options.storiesGlob]
  const ROUTE = '/.figma/make/kit.html'
  const VIRTUAL_ID = 'virtual:figma-stories'
  const RESOLVED_ID = '\0' + VIRTUAL_ID
  const STORIES_MODULE = `export const stories = import.meta.glob(${JSON.stringify(storiesGlob)})`
  const HTML_BOOTSTRAP = `<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
</head>
<body>
<div id="figma-make-kit-root"></div>
<script type="module">
  import { stories } from 'virtual:figma-stories'
  window.__FIGMA__ = Object.assign(window.__FIGMA__ ?? {}, { stories })
  window.dispatchEvent(new CustomEvent('figma.ready'))
</script>
</body>
</html>`

  return {
    name: 'figma-make-kit',
    apply: 'serve',
    resolveId(id) {
      if (id === VIRTUAL_ID) return RESOLVED_ID
      return null
    },
    load(id) {
      if (id !== RESOLVED_ID) return null
      return STORIES_MODULE
    },
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = req.url || ''
        if (url.split('?')[0] !== ROUTE) return next()

        try {
          res.setHeader('Content-Type', 'text/html')
          res.end(await server.transformIndexHtml(url, HTML_BOOTSTRAP))
        } catch (err) {
          next(err as Error)
        }
      })
    },
  }
}

/**
 * Reports the sources of dependencies linked from outside node_modules (pnpm
 * or npm workspaces, `file:`, `link:`) under `node_modules/<name>/`, the way
 * installed packages appear in sourcemaps. Vite otherwise reports their real
 * path, such as `libraries/<name>/`.
 */
function figmaLinkedPackageSourcemaps(): Plugin {
  const packageJson = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, 'package.json'), 'utf8'))
  const linkedPackages = Object.keys({ ...packageJson.dependencies, ...packageJson.devDependencies }).flatMap((name) => {
    const installedDir = path.resolve(import.meta.dirname, 'node_modules', name)
    try {
      const realDir = fs.realpathSync(installedDir)
      return realDir.split(path.sep).includes('node_modules') ? [] : [{ installedDir, realDir }]
    } catch {
      return []
    }
  })
  const sourceMappingUrl = /\/\/# sourceMappingURL=(\S+)\s*$/

  function installedPath(file: string) {
    const linked = linkedPackages.find(({ realDir }) => file.startsWith(realDir + path.sep))
    return linked && path.join(linked.installedDir, path.relative(linked.realDir, file))
  }
  function readSourceMap(file: string, code: string) {
    const url = sourceMappingUrl.exec(code)?.[1]
    try {
      if (url?.startsWith('data:')) {
        return { map: JSON.parse(Buffer.from(url.split(',')[1], 'base64').toString()), mapDir: path.dirname(file) }
      }
      if (url) {
        const mapFile = path.resolve(path.dirname(file), url)
        return { map: JSON.parse(fs.readFileSync(mapFile, 'utf8')), mapDir: path.dirname(mapFile) }
      }
    } catch {}
    // Without a usable input map, map every line to itself.
    const mappings = code.split('\n').map((_, i) => (i ? 'AACA' : 'AAAA'))
    const map = { version: 3, sources: [file], sourcesContent: [code], names: [], mappings: mappings.join(';') }
    return { map, mapDir: path.dirname(file) }
  }

  return {
    name: 'figma-linked-package-sourcemaps',
    enforce: 'pre',
    load(id) {
      // Leave queried imports such as ?raw and ?url to Vite's own loaders.
      if (id.includes('?') || !/\.[cm]?[jt]sx?$/.test(id) || !installedPath(id)) return null

      const code = fs.readFileSync(id, 'utf8')
      const { map, mapDir } = readSourceMap(id, code)
      const sourceRoot = path.resolve(mapDir, map.sourceRoot ?? '')
      map.sources = map.sources.map((source: string) => {
        const original = path.resolve(sourceRoot, source)
        return installedPath(original) ?? original
      })
      delete map.sourceRoot
      return { code: code.replace(sourceMappingUrl, ''), map }
    },
  }
}

/**
 * Custom Nodemailer Team Invitation Plugin
 * Dispatches HTML team invitation emails using Nodemailer.
 */
async function getMailTransporter(nodemailer: any, env: Record<string, string>) {
  const smtpUser = env.SMTP_USER || process.env.SMTP_USER || ''
  const smtpPass = env.SMTP_PASSWORD || process.env.SMTP_PASSWORD || ''
  const smtpHost = env.SMTP_HOST || process.env.SMTP_HOST || 'smtp.gmail.com'
  const smtpPort = parseInt(env.SMTP_PORT || process.env.SMTP_PORT || '465')
  const smtpSecure = (env.SMTP_SECURE || process.env.SMTP_SECURE) === 'true' || smtpPort === 465

  if (smtpUser && smtpPass) {
    const isGmail = smtpHost.includes('gmail')
    console.log(`[Meetora Nodemailer] 🚀 Using SMTP (${isGmail ? 'Gmail' : smtpHost}) as ${smtpUser}`)
    return {
      transporter: nodemailer.createTransport({
        service: isGmail ? 'gmail' : undefined,
        host: isGmail ? undefined : smtpHost,
        port: smtpPort,
        secure: smtpSecure,
        auth: {
          user: smtpUser,
          pass: smtpPass,
        },
      }),
      fromEmail: smtpUser,
      isReal: true,
    }
  }

  console.log(`[Meetora Nodemailer] ℹ️ Real SMTP credentials not in .env (SMTP_USER/SMTP_PASSWORD empty). Using in-memory test transporter.`)
  return {
    transporter: nodemailer.createTransport({
      jsonTransport: true,
    }),
    fromEmail: smtpUser || 'no-reply@meetora.ai',
    isReal: false,
  }
}

function nodemailerInvitePlugin(env: Record<string, string> = {}): Plugin {
  return {
    name: 'nodemailer-invite-plugin',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = req.url?.split('?')[0] || ''
        if (req.method === 'POST' && url === '/api/invite-team-member') {
          let body = ''
          req.on('data', (chunk: Buffer) => {
            body += chunk.toString()
          })
          req.on('end', async () => {
            try {
              const data = JSON.parse(body || '{}')
              const { email, name, role, teamName, inviterName } = data

              if (!email || !email.includes('@')) {
                res.statusCode = 400
                res.setHeader('Content-Type', 'application/json')
                return res.end(JSON.stringify({ error: 'Valid email address is required' }))
              }

              const nodemailerModule = await import('nodemailer')
              const nodemailer = nodemailerModule.default || nodemailerModule

              const { transporter, fromEmail, isReal } = await getMailTransporter(nodemailer, env)

              const htmlContent = `
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 28px; border: 1px solid #e0e7ff; border-radius: 14px; background: #ffffff;">
                  <div style="background: linear-gradient(135deg, #6d55d8, #7c3aed); padding: 26px; border-radius: 10px; text-align: center; color: #ffffff;">
                    <h1 style="margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.5px;">Meetora AI Meeting Analyzer</h1>
                    <p style="margin: 6px 0 0; font-size: 13px; opacity: 0.9;">Multi-Speaker Acoustic Intelligence & Action Tracking</p>
                  </div>
                  <div style="padding: 24px 6px; color: #333333; line-height: 1.6;">
                    <h2 style="color: #1e1b4b; font-size: 18px; margin-top: 0;">You've been invited to join ${teamName || 'Meetora Team'}</h2>
                    <p>Hello <b>${name || 'Team Member'}</b>,</p>
                    <p><b>${inviterName || 'Jordan Davis'}</b> has invited you to join their workspace team as <b>${role || 'Collaborator'}</b>.</p>
                    <div style="background: #f8f7ff; border-left: 4px solid #7c3aed; padding: 14px 18px; margin: 20px 0; border-radius: 6px;">
                      <p style="margin: 0; font-size: 13px; font-weight: 700; color: #5b21b6;">Included Workspace Capabilities:</p>
                      <ul style="margin: 8px 0 0; padding-left: 18px; font-size: 13px; color: #4c1d95;">
                        <li>Multi-speaker voice biometric identification (pyannote.audio)</li>
                        <li>Automated OpenAI Whisper speech-to-text with timestamps</li>
                        <li>Custom DistilBERT intent extraction (Actions & Decisions)</li>
                        <li>1-Click Google Calendar deadline sync & Celery email reminders</li>
                      </ul>
                    </div>
                    <div style="text-align: center; margin: 28px 0;">
                      <a href="http://localhost:5173/#register?email=${encodeURIComponent(email)}" style="background: #6d55d8; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; display: inline-block;">
                        Accept Invitation & Join Team
                      </a>
                    </div>
                    <p style="font-size: 12px; color: #888888; text-align: center; margin-bottom: 0;">If the button doesn't open, visit: http://localhost:5173/#register?email=${encodeURIComponent(email)}</p>
                  </div>
                  <div style="border-top: 1px solid #f0f0f0; padding-top: 16px; font-size: 11px; color: #999999; text-align: center;">
                    Sent securely via Nodemailer Engine · Meetora Platform
                  </div>
                </div>
              `

              const result = await transporter.sendMail({
                from: `"Meetora Team" <${fromEmail}>`,
                to: email,
                subject: `Invitation: Join ${teamName || 'Meetora'} on Meetora AI Meeting Analyzer`,
                text: `Hello ${name || 'Team Member'},\n\n${inviterName || 'Jordan Davis'} invited you to join their team as ${role || 'Collaborator'}.\n\nAccept your invitation at: http://localhost:5173/#register?email=${encodeURIComponent(email)}`,
                html: htmlContent,
              })

              console.log(`\n📧 [Meetora Nodemailer] Invitation email sent to: ${email}`)
              console.log(`📡 [Transport]: ${isReal ? 'Delivered via live SMTP' : 'Simulated (Set SMTP_USER & SMTP_PASSWORD in .env for real inbox delivery)'}\n`)

              res.statusCode = 200
              res.setHeader('Content-Type', 'application/json')
              return res.end(JSON.stringify({
                success: true,
                message: `Invitation email sent successfully to ${email} via Nodemailer!`,
                messageId: result.messageId || 'meetora_' + Date.now(),
                recipient: email,
                transport: isReal ? 'Live SMTP' : 'Nodemailer Test',
              }))
            } catch (err: any) {
              console.error('Nodemailer invite error:', err)
              res.statusCode = 500
              res.setHeader('Content-Type', 'application/json')
              return res.end(JSON.stringify({ error: err.message || 'Failed to dispatch email' }))
            }
          })
          return
        }

        if (req.method === 'POST' && url === '/api/forgot-password') {
          let body = ''
          req.on('data', (chunk: Buffer) => {
            body += chunk.toString()
          })
          req.on('end', async () => {
            try {
              const data = JSON.parse(body || '{}')
              const { email, token, reset_url } = data

              if (!email || !email.includes('@')) {
                res.statusCode = 400
                res.setHeader('Content-Type', 'application/json')
                return res.end(JSON.stringify({ error: 'Valid email address is required' }))
              }

              const nodemailerModule = await import('nodemailer')
              const nodemailer = nodemailerModule.default || nodemailerModule

              const { transporter, fromEmail, isReal } = await getMailTransporter(nodemailer, env)

              const resetToken = token || ('rst_' + Math.random().toString(36).substring(2) + Date.now().toString(36))
              const resetUrl = reset_url || `http://localhost:5173/#forgot?token=${resetToken}&email=${encodeURIComponent(email)}`

              const htmlContent = `
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 28px; border: 1px solid #e0e7ff; border-radius: 14px; background: #ffffff;">
                  <div style="background: linear-gradient(135deg, #4f46e5, #7c3aed); padding: 26px; border-radius: 10px; text-align: center; color: #ffffff;">
                    <h1 style="margin: 0; font-size: 22px; font-weight: 700;">Meetora Password Reset</h1>
                    <p style="margin: 6px 0 0; font-size: 13px; opacity: 0.9;">Secure Account Authentication</p>
                  </div>
                  <div style="padding: 24px 6px; color: #333333; line-height: 1.6;">
                    <h2 style="color: #1e1b4b; font-size: 18px; margin-top: 0;">Reset Your Password</h2>
                    <p>We received a request to reset your password for your Meetora account (<b>${email}</b>).</p>
                    <p>Click the secure button below to set a new password. This link is valid for 60 minutes.</p>
                    <div style="text-align: center; margin: 28px 0;">
                      <a href="${resetUrl}" style="background: #4f46e5; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; display: inline-block;">
                        Reset Password
                      </a>
                    </div>
                    <p style="font-size: 12px; color: #888888; text-align: center; margin-bottom: 0;">If you did not request this, please ignore this email.</p>
                  </div>
                  <div style="border-top: 1px solid #f0f0f0; padding-top: 16px; font-size: 11px; color: #999999; text-align: center;">
                    Sent securely via Nodemailer Engine · Meetora Platform
                  </div>
                </div>
              `

              const result = await transporter.sendMail({
                from: `"Meetora Security" <${fromEmail}>`,
                to: email,
                subject: 'Reset your Meetora account password',
                text: `Click the link to reset your password: ${resetUrl}`,
                html: htmlContent,
              })

              console.log(`\n======================================================`)
              console.log(`📧 [Meetora Nodemailer] Password reset dispatched for: ${email}`)
              console.log(`🔗 [Meetora Nodemailer] Reset URL: ${resetUrl}`)
              console.log(`📡 [Transport]: ${isReal ? 'Delivered via live SMTP' : 'Simulated (Set SMTP_USER & SMTP_PASSWORD in .env for inbox delivery)'}`)
              console.log(`======================================================\n`)

              res.statusCode = 200
              res.setHeader('Content-Type', 'application/json')
              return res.end(JSON.stringify({
                success: true,
                message: `Password reset link sent to ${email} via Nodemailer!`,
                resetToken,
                resetUrl,
                messageId: result.messageId || 'reset_' + Date.now(),
                transport: isReal ? 'Live SMTP' : 'Nodemailer Test',
              }))
            } catch (err: any) {
              console.error('Nodemailer reset error:', err)
              res.statusCode = 500
              res.setHeader('Content-Type', 'application/json')
              return res.end(JSON.stringify({ error: err.message || 'Failed to dispatch reset email' }))
            }
          })
          return
        }
        next()
      })
    },
  }
}
