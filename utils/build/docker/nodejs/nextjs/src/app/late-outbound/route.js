import http from 'http'
import net from 'net'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

const lateOutboundServer = net.createServer(socket => {
  socket.once('data', () => {
    socket.end('HTTP/1.1 202 Accepted\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok')
  })
})

let lateOutboundPortPromise

function getLateOutboundPort () {
  if (!lateOutboundPortPromise) {
    lateOutboundPortPromise = new Promise((resolve, reject) => {
      lateOutboundServer.once('error', reject)
      lateOutboundServer.listen(0, '127.0.0.1', () => {
        resolve(lateOutboundServer.address().port)
      })
    })
  }

  return lateOutboundPortPromise
}

export async function GET () {
  const lateOutboundPort = await getLateOutboundPort()
  const tracer = global._ddtrace
  const activeSpan = tracer?.scope().active()
  const rootSpan = activeSpan?.context()._trace.started[0] || activeSpan

  setTimeout(() => {
    tracer?.scope().activate(rootSpan, () => {
      http.get(`http://127.0.0.1:${lateOutboundPort}/intake/v2/events`, response => {
        response.resume()
      }).on('error', error => {
        console.error('Late outbound request failed:', error)
      })
    })
  }, 250)

  return new NextResponse('late-outbound', { status: 200 })
}
