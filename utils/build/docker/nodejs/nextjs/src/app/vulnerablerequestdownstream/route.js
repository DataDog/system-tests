import { NextResponse } from 'next/server'
import axios from 'axios'
const crypto = require('crypto')

export const dynamic = 'force-dynamic'

export async function GET () {
  try {
    crypto.createHash('md5').update('password').digest('hex')
    const resFetch = await axios.get('http://127.0.0.1:7777/returnheaders')
    return NextResponse.json(resFetch.data)
  } catch (e) {
    return NextResponse.json({ message: e.toString(), status_code: 500 })
  }
}
