import { NextResponse } from 'next/server'
import axios from 'axios'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  try {
    const headers = Object.fromEntries(request.headers.entries())
    const resFetch = await axios.get('http://localhost:7777/returnheaders', {
      headers
    })

    return NextResponse.json(resFetch.data)
  } catch (e) {
    return NextResponse.json({ message: e.toString(), status_code: 500 })
  }
}
